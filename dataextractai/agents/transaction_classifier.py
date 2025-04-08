"""
Transaction Classifier Agent

This module implements the AI-based transaction classification system using a three-pass approach:
1. Payee identification
2. Category assignment
3. Classification (business vs personal)

The classifier uses the client's business profile for context and can suggest new categories
when needed. It also provides reasoning for all classifications.
"""

import os
import json
import pandas as pd
from typing import Dict, List, Optional, Any
from openai import OpenAI
from ..utils.config import (
    ASSISTANTS_CONFIG,
    PROMPTS,
    STANDARD_CATEGORIES,
    CLASSIFICATIONS,
)
from .client_profile_manager import ClientProfileManager
from ..models.ai_responses import (
    PayeeResponse,
    CategoryResponse,
    ClassificationResponse,
)
from ..db.client_db import ClientDB
import sqlite3
import logging
from tools.vendor_lookup import lookup_vendor_info, format_vendor_results
from ..utils.tax_categories import (
    TAX_WORKSHEET_CATEGORIES,
    get_worksheet_for_category,
    get_line_number,
    is_valid_category,
)
from ..models.worksheet_models import WorksheetAssignment, WorksheetPrompt
from datetime import datetime
from colorama import Fore, Style, init
import difflib
import traceback
from dataclasses import dataclass
from thefuzz import fuzz
import re

# Initialize colorama
init(autoreset=True)

logger = logging.getLogger(__name__)


# Configure a better logging format
class ColoredFormatter(logging.Formatter):
    """Custom formatter adding colors to log messages based on level."""

    FORMATS = {
        logging.DEBUG: Fore.CYAN + "[DEBUG] %(message)s" + Style.RESET_ALL,
        logging.INFO: "%(message)s",
        logging.WARNING: Fore.YELLOW + "[WARN] %(message)s" + Style.RESET_ALL,
        logging.ERROR: Fore.RED + "[ERROR] %(message)s" + Style.RESET_ALL,
        logging.CRITICAL: Fore.RED
        + Style.BRIGHT
        + "[CRIT] %(message)s"
        + Style.RESET_ALL,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


# Apply the custom formatter if not already configured
for handler in logger.handlers:
    handler.setFormatter(ColoredFormatter())
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter())
    logger.addHandler(handler)


@dataclass
class TransactionInfo:
    """Class to hold transaction information during processing."""

    transaction_id: str
    description: str
    amount: float
    transaction_date: str
    payee_info: Optional[PayeeResponse] = None
    category_info: Optional[CategoryResponse] = None
    tax_info: Optional[ClassificationResponse] = None

    def __str__(self):
        return f"[Transaction {self.transaction_id}]"


@dataclass
class TaxInfo:
    """Tax classification information for a transaction."""

    tax_category_id: int  # Changed from tax_category: str
    tax_category: str  # Keep this for display/logging purposes
    business_percentage: int
    worksheet: str
    confidence: str
    reasoning: str


class TransactionClassifier:
    def __init__(self, client_name: str):
        """Initialize the transaction classifier."""
        self.client = OpenAI()
        self.client_name = client_name
        self.profile_manager = ClientProfileManager(client_name)

        # Initialize database connection management
        self._persistent_conn = None
        self._transaction_active = False

        # Ensure client exists in database
        if not self.profile_manager.db.execute_query(
            "SELECT id FROM clients WHERE name = ?", (client_name,)
        ):
            # Create client if doesn't exist
            self.profile_manager.db.execute_query(
                "INSERT INTO clients (name) VALUES (?)", (client_name,)
            )
            logger.info(f"Created new client record for '{client_name}'")

        self.business_profile = self.profile_manager._load_profile()

        if not self.business_profile:
            raise ValueError(
                f"No business profile found for client '{client_name}'. Please create a profile first."
            )

        # Get client ID from the database
        self.client_id = self.profile_manager.db.get_client_id(client_name)
        if not self.client_id:
            raise ValueError(
                f"No client ID found for client '{client_name}'. Please ensure the client exists in the database."
            )

        self.business_context = self._get_business_context()
        self._load_standard_categories()
        self._load_client_categories()

    def _load_standard_categories(self) -> None:
        """Load standard tax categories."""
        try:
            # Load standard categories from config
            self.standard_categories = STANDARD_CATEGORIES

            # Load tax worksheet categories
            self.tax_categories = TAX_WORKSHEET_CATEGORIES

            # Initialize tax categories in the database using '6A' as the default worksheet
            for worksheet_key, categories in TAX_WORKSHEET_CATEGORIES.items():
                # Handle categories as a list
                if isinstance(categories, list):
                    for category in categories:
                        # Insert the category if it doesn't exist, using '6A' as the worksheet
                        self.profile_manager.db.execute_query(
                            """INSERT OR IGNORE INTO tax_categories 
                               (name, worksheet) VALUES (?, ?)""",
                            (category, "6A"),  # Use '6A' instead of worksheet_key
                        )

            # Verify tax categories were initialized
            result = self.profile_manager.db.execute_query(
                "SELECT COUNT(*) FROM tax_categories"
            )
            count = result[0][0] if result else 0

            if count == 0:
                logger.warning(
                    "No tax categories found in database after initialization"
                )
                # Force insert of categories using '6A' worksheet
                for worksheet_key, categories in TAX_WORKSHEET_CATEGORIES.items():
                    if isinstance(categories, list):
                        for category in categories:
                            self.profile_manager.db.execute_query(
                                """INSERT INTO tax_categories 
                                   (name, worksheet) VALUES (?, ?)""",
                                (category, "6A"),  # Use '6A' instead of worksheet_key
                            )
                logger.info("Forced initialization of tax categories")
            else:
                logger.info(f"Found {count} tax categories in database")

            # Log all categories for debugging
            categories = self.profile_manager.db.execute_query(
                "SELECT id, name, worksheet FROM tax_categories ORDER BY id"
            )
            if categories:
                logger.debug("Tax Categories:")
                for cat in categories:
                    logger.debug(f"  ID {cat[0]}: {cat[1]} ({cat[2]})")

        except Exception as e:
            logger.error(f"Error loading standard categories: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _get_business_context(self) -> str:
        """Get business context from profile for AI prompts."""
        if not self.business_profile:
            return ""

        context_parts = []

        # Add business type and description
        if self.business_profile.get("business_type"):
            context_parts.append(
                f"Business Type: {self.business_profile['business_type']}"
            )
        if self.business_profile.get("business_description"):
            context_parts.append(
                f"Business Description: {self.business_profile['business_description']}"
            )

        # Add industry insights if available
        if self.business_profile.get("industry_insights"):
            context_parts.append(
                f"Industry Insights: {self.business_profile['industry_insights']}"
            )

        # Add any custom categories
        if self.business_profile.get("custom_categories"):
            categories = self.business_profile["custom_categories"]
            if isinstance(categories, list):
                context_parts.append(f"Custom Categories: {', '.join(categories)}")

        return "\n".join(context_parts)

    def _get_model(self) -> str:
        """Get the OpenAI model to use from environment variables.

        Returns the appropriate model based on environment configuration:
        - OPENAI_MODEL_FAST for faster, less precise operations
        - OPENAI_MODEL_PRECISE for operations requiring more accuracy
        """
        # Default to FAST model unless specified otherwise
        model_type = os.getenv("OPENAI_MODEL_TYPE", "FAST")
        if model_type.upper() == "PRECISE":
            return os.getenv("OPENAI_MODEL_PRECISE")
        return os.getenv("OPENAI_MODEL_FAST")

    def _find_matching_transaction(self, description: str) -> Optional[Dict[str, Any]]:
        """Find a matching transaction in the database."""
        try:
            logger.info(f"🔍 Searching for match: {description}")

            # First try exact match
            query = """
                SELECT tc.payee, tc.category, tc.category_confidence, tc.tax_category, 
                       tc.business_percentage, tc.worksheet, tc.classification, tc.classification_confidence
                FROM normalized_transactions nt
                JOIN transaction_classifications tc ON nt.transaction_id = tc.transaction_id
                WHERE nt.client_id = ? AND nt.description = ?
                ORDER BY nt.transaction_date DESC
                LIMIT 1
            """
            result = self.profile_manager.db.execute_query(
                query, (self.client_id, description)
            )

            if result:
                logger.info(f"✅ Found exact match for description: {description}")
                row = result[0]
                return {
                    "payee": row[0],
                    "category": row[1],
                    "category_confidence": row[2],
                    "tax_category": row[3],
                    "business_percentage": row[4],
                    "worksheet": row[5],
                    "classification": row[6],
                    "classification_confidence": row[7],
                }

            # If no exact match, try matching based on store name and location pattern
            store_name = self._extract_store_name(description)
            if store_name:
                logger.info(f"📍 Extracted store name: {store_name}")
                # Extract location if present (usually at the end after the store name)
                location_match = re.search(
                    r"(?:^|\s)(?:IN|AT|OF|-)?\s*([A-Z\s]+(?:,\s*[A-Z]{2})?)$",
                    description,
                )
                location = location_match.group(1) if location_match else None

                if location:
                    logger.info(f"📍 Extracted location: {location}")
                    # Match store name AND location
                    pattern = f"{store_name}%{location}"
                    logger.info(f"🔍 Trying to match pattern: {pattern}")
                    query = """
                        SELECT tc.payee, tc.category, tc.category_confidence, tc.tax_category, 
                               tc.business_percentage, tc.worksheet, tc.classification, tc.classification_confidence,
                               nt.description
                        FROM normalized_transactions nt
                        JOIN transaction_classifications tc ON nt.transaction_id = tc.transaction_id
                        WHERE nt.client_id = ? AND nt.description LIKE ?
                        ORDER BY nt.transaction_date DESC
                        LIMIT 1
                    """
                    result = self.profile_manager.db.execute_query(
                        query, (self.client_id, pattern)
                    )

                    if result:
                        # Calculate similarity score between descriptions
                        similarity = fuzz.ratio(description, result[0][8])
                        logger.info(
                            f"📊 Similarity score with {result[0][8]}: {similarity}%"
                        )
                        if similarity >= 80:  # Only use matches with high similarity
                            logger.info(
                                f"✅ Found store+location match with {similarity}% similarity: {result[0][8]}"
                            )
                            row = result[0]
                            return {
                                "payee": row[0],
                                "category": row[1],
                                "category_confidence": row[2],
                                "tax_category": row[3],
                                "business_percentage": row[4],
                                "worksheet": row[5],
                                "classification": row[6],
                                "classification_confidence": row[7],
                            }
                        else:
                            logger.info(
                                f"❌ Similarity score too low ({similarity}%), not using match"
                            )

            logger.info(f"❌ No matching transaction found for: {description}")
            return None

        except Exception as e:
            logger.error(f"Error finding matching transaction: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def _extract_store_name(self, description: str) -> Optional[str]:
        """Extract the store name from a transaction description."""
        # Remove common transaction-specific details
        parts = description.split()
        if not parts:
            return None

        # Return first part as store name, removing any trailing numbers
        store_name = re.sub(r"\d+$", "", parts[0]).strip()
        return store_name if store_name else None

    def _get_payee(
        self, description: str, force_process: bool = False
    ) -> PayeeResponse:
        """Get the payee for a transaction description."""
        if not force_process:
            # Only check for matches if not forcing LLM processing
            match_data = self._find_matching_transaction(description)
            if match_data:
                return PayeeResponse(
                    payee=match_data["payee"],
                    confidence="high",
                    reasoning=f"Using existing payee from matching transaction",
                    business_description=match_data.get("business_description", ""),
                    general_category=match_data.get("general_category", ""),
                )

        # If force_process=True or no match found, use LLM
        prompt = self._build_payee_prompt(description)
        response = self.client.chat.completions.create(
            model=self._get_model(),
            messages=[
                {
                    "role": "system",
                    "content": "You are a transaction classification assistant that provides JSON responses.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=200,
        )

        result = json.loads(response.choices[0].message.content)
        return PayeeResponse(**result)

    def _get_classification(
        self,
        transaction_description: str,
        amount: float,
        date: str,
        payee: str,
        category: str,
        force_process: bool = False,
        row_info: str = "",
    ) -> ClassificationResponse:
        """Get classification for a transaction."""
        try:
            # First try to find a matching transaction
            match_data = self._find_matching_transaction(transaction_description)
            if match_data:
                logger.info(
                    f"{row_info} ✓ Using existing classification: {match_data['classification']}"
                )
                return ClassificationResponse(
                    tax_category=match_data["tax_category"],
                    business_percentage=match_data["business_percentage"],
                    worksheet=match_data["worksheet"],
                    confidence=match_data["classification_confidence"],
                    reasoning="Using existing classification from database",
                )

            # Build the prompt
            prompt = self._build_classification_prompt(
                transaction_description,
                payee,
                category,
                amount,
                date,
            )

            # Get response from LLM
            response = self.client.chat.completions.create(
                model=self._get_model(),
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a transaction classification assistant that provides JSON responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            result = json.loads(response.choices[0].message.content)
            return ClassificationResponse(**result)

        except Exception as e:
            logger.error(f"{row_info} ❌ Error in classification: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _start_batch_processing(self):
        """Start batch processing by establishing a persistent connection."""
        if not self._persistent_conn:
            self._persistent_conn = sqlite3.connect(self.profile_manager.db.db_path)
            # Configure connection for optimal performance and reliability
            self._persistent_conn.execute("PRAGMA journal_mode=WAL")
            self._persistent_conn.execute("PRAGMA synchronous=NORMAL")
            self._persistent_conn.execute("PRAGMA foreign_keys=ON")
            # Log current settings
            cursor = self._persistent_conn.execute("PRAGMA journal_mode")
            logger.info(f"SQLite journal mode: {cursor.fetchone()[0]}")
            cursor = self._persistent_conn.execute("PRAGMA synchronous")
            logger.info(f"SQLite synchronous mode: {cursor.fetchone()[0]}")
            logger.info("Established persistent connection for batch processing")

    def _start_transaction(self, row_info: str):
        """Start a new transaction if one isn't already active."""
        if self._persistent_conn and not self._transaction_active:
            self._persistent_conn.execute("BEGIN")
            self._transaction_active = True
            logger.debug(f"{row_info} Started new transaction")

    def _commit_transaction(self, row_info: str):
        """Commit the current transaction if one is active."""
        if self._persistent_conn and self._transaction_active:
            try:
                self._persistent_conn.commit()
                logger.debug(f"{row_info} Committed transaction")
            except Exception as e:
                logger.error(f"{row_info} Error committing transaction: {e}")
                self._persistent_conn.rollback()
                logger.debug(f"{row_info} Rolled back transaction")
            finally:
                self._transaction_active = False

    def _end_batch_processing(self):
        """End batch processing by closing the persistent connection."""
        if self._persistent_conn:
            try:
                # Commit any pending changes
                self._persistent_conn.commit()
                logger.debug("Committed final transaction")
            except Exception as e:
                logger.error(f"Error committing final transaction: {e}")
                self._persistent_conn.rollback()
            finally:
                self._persistent_conn.close()
                self._persistent_conn = None
                logger.debug("Closed persistent connection for batch processing")

    def _commit_pass(self, pass_num: int, transaction: TransactionInfo) -> None:
        """Commit the results of a pass to the database."""
        try:
            if pass_num == 1:
                self.profile_manager.db.execute_query(
                    """UPDATE transaction_classifications 
                       SET payee = ?, payee_confidence = ?, payee_reasoning = ?,
                           business_description = ?, general_category = ?
                       WHERE transaction_id = ?""",
                    (
                        transaction.payee_info.payee,
                        transaction.payee_info.confidence,
                        transaction.payee_info.reasoning,
                        transaction.payee_info.business_description,
                        transaction.payee_info.general_category,
                        transaction.transaction_id,
                    ),
                )
                logger.info(
                    f"✓ Pass 1 complete: {transaction.payee_info.payee} ({transaction.payee_info.confidence})"
                )

            elif pass_num == 2:
                self.profile_manager.db.execute_query(
                    """UPDATE transaction_classifications 
                       SET category = ?, category_confidence = ?, category_reasoning = ?
                       WHERE transaction_id = ?""",
                    (
                        transaction.category_info.category,
                        transaction.category_info.confidence,
                        transaction.category_info.notes,
                        transaction.transaction_id,
                    ),
                )
                logger.info(
                    f"✓ Pass 2 complete: {transaction.category_info.category} ({transaction.category_info.confidence})"
                )

            elif pass_num == 3:
                self.profile_manager.db.execute_query(
                    """UPDATE transaction_classifications 
                       SET tax_category_id = ?, business_percentage = ?, 
                           worksheet = ?, classification_confidence = ?,
                           classification_reasoning = ?
                       WHERE transaction_id = ?""",
                    (
                        transaction.tax_info.tax_category_id,  # Using ID instead of name
                        transaction.tax_info.business_percentage,
                        transaction.tax_info.worksheet,
                        transaction.tax_info.confidence,
                        transaction.tax_info.reasoning,
                        transaction.transaction_id,
                    ),
                )
                # Get tax category name from ID for logging
                tax_cat_query = "SELECT name FROM tax_categories WHERE id = ?"
                tax_cat_result = self.profile_manager.db.execute_query(
                    tax_cat_query, (transaction.tax_info.tax_category_id,)
                )
                tax_category_name = (
                    tax_cat_result[0][0] if tax_cat_result else "Unknown"
                )

                logger.info(
                    f"✓ Pass 3 complete: {tax_category_name} ({transaction.tax_info.confidence})"
                )

            # Use the connection from the persistent connection pool
            if self._persistent_conn:
                self._persistent_conn.commit()
            else:
                # If no persistent connection, commit using the profile manager's connection
                self.profile_manager.db.execute_query("COMMIT")

        except Exception as e:
            logger.error(f"Error committing pass {pass_num}: {str(e)}")
            if self._persistent_conn:
                self._persistent_conn.rollback()
            raise

    def _load_client_categories(self) -> List[str]:
        """Load client-specific categories from the database."""
        with sqlite3.connect(self.profile_manager.db.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT category_name 
                FROM client_expense_categories 
                WHERE client_id = ? AND tax_year = strftime('%Y', 'now')
                """,
                (self.client_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def _clean_description(self, description: str) -> str:
        """Clean a transaction description for better matching."""
        clean_desc = description.strip()

        # Remove common transaction prefixes/suffixes
        prefixes = [
            "POS ",
            "PURCHASE ",
            "PMT ",
            "PAYMENT ",
            "TXN ",
            "TERMINAL ",
            "VBASE2 ",
            "IN ",
        ]
        clean_desc = clean_desc.upper()
        for prefix in prefixes:
            if clean_desc.startswith(prefix):
                clean_desc = clean_desc[len(prefix) :]

        # Remove special characters but keep spaces
        clean_desc = re.sub(r"[^A-Z0-9 ]", "", clean_desc)

        # Remove multiple spaces
        clean_desc = " ".join(clean_desc.split())

        return clean_desc

    def _get_cache_key(
        self,
        description: str,
        payee: str = None,
        category: str = None,
        pass_type: str = None,
    ) -> str:
        """Generate a consistent cache key."""
        # Start with the store name
        store_name = self._extract_store_name(description)
        if not store_name:
            store_name = description.upper()

        # Build key parts
        key_parts = [store_name]
        if payee:
            key_parts.append(payee.upper())
        if category:
            key_parts.append(category.upper())
        if pass_type:
            key_parts.append(pass_type.upper())

        # Join with pipe delimiter for consistency
        return "|".join(key_parts)

    def _get_cached_result(
        self, cache_key: str, pass_type: str = None
    ) -> Optional[Dict]:
        """Get cached result for a given key and pass type."""
        try:
            logger.debug(f"Checking cache for key: {cache_key}")
            if pass_type:
                logger.debug(f"Filtering by pass_type: {pass_type}")

            query = """
                SELECT result
                FROM transaction_cache 
                WHERE client_id = ? AND cache_key = ?
            """
            params = [self.client_id, cache_key]

            if pass_type:
                query += " AND pass_type = ?"
                params.append(pass_type)

            query += " ORDER BY created_at DESC LIMIT 1"

            result = self.profile_manager.db.execute_query(query, params)
            if result and result[0]:
                cached = json.loads(result[0][0])
                logger.debug(f"Found cache entry: {cached}")
                return cached

            logger.debug("No cache entry found")
            return None

        except Exception as e:
            logger.error(f"Error retrieving from cache: {str(e)}")
            return None

    def _cache_result(
        self, cache_key: str, result: Dict, pass_type: str = "test"
    ) -> None:
        """Cache a result for future use."""
        if not cache_key or not result:
            return

        try:
            # Convert result to JSON
            result_json = json.dumps(result)

            # Insert or update cache entry
            upsert_query = """
                INSERT INTO transaction_cache (client_id, cache_key, result, pass_type)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (client_id, cache_key, pass_type) DO UPDATE SET
                    result = excluded.result
            """

            self.profile_manager.db.execute_query(
                upsert_query, (self.client_id, cache_key, result_json, pass_type)
            )
            logger.info(f"💾 Cache write successful for key: {cache_key}")

            # Verify write
            verify = self._get_cached_result(cache_key)
            if verify:
                logger.info("✅ Cache write verified")
            else:
                logger.warning("⚠️ Cache write verification failed")

        except Exception as e:
            logger.error(f"❌ Cache write failed: {str(e)}")

    def process_transactions(
        self,
        transactions: pd.DataFrame,
        resume_from_pass: int = 1,
        force_process: bool = False,
        batch_size: int = 10,
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
    ) -> None:
        """Process transactions through multiple passes."""
        try:
            # Start batch processing with persistent connection
            self._start_batch_processing()

            if not isinstance(transactions, pd.DataFrame):
                raise ValueError("transactions must be a pandas DataFrame")

            if resume_from_pass < 1 or resume_from_pass > 3:
                raise ValueError("resume_from_pass must be between 1 and 3")

            # Handle row range
            start_row = start_row if start_row is not None else 0
            end_row = end_row if end_row is not None else len(transactions)

            if start_row < 0 or end_row > len(transactions) or start_row >= end_row:
                raise ValueError("Invalid row range specified")

            total_transactions = end_row - start_row
            pass_desc = {
                1: "Payee identification",
                2: "Category assignment",
                3: "Final classification & tax mapping",
            }

            logger.info(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")
            logger.info(
                f"{Fore.GREEN}▶ Starting transaction processing for {self.client_name}{Style.RESET_ALL}"
            )
            logger.info(
                f"  • Processing {total_transactions} transactions (rows {start_row+1}-{end_row})"
            )
            logger.info(
                f"  • Starting from pass {resume_from_pass}: {pass_desc.get(resume_from_pass, '')}"
            )
            logger.info(f"  • Force processing: {force_process}")
            logger.info(f"{Fore.GREEN}{'='*80}{Style.RESET_ALL}\n")

            # Stats counters
            stats = {
                "pass1_processed": 0,
                "pass2_processed": 0,
                "pass3_processed": 0,
                "errors": [],
            }

            # Process transactions row by row
            for idx in range(start_row, end_row):
                row = transactions.iloc[idx]
                row_number = idx + 1

                try:
                    # Create TransactionInfo object
                    transaction = TransactionInfo(
                        transaction_id=str(row.transaction_id),
                        description=row.description,
                        amount=float(row.amount),
                        transaction_date=row.transaction_date.strftime("%Y-%m-%d"),
                    )

                    # Log separator for visual clarity
                    logger.info(f"\n{Fore.CYAN}{'─'*80}{Style.RESET_ALL}")
                    logger.info(
                        f"{Fore.CYAN}[Row {row_number}] Transaction: {transaction.description}{Style.RESET_ALL}"
                    )

                    # Pass 1: Payee identification
                    if resume_from_pass <= 1:
                        logger.info(
                            f"{Fore.GREEN}▶ PASS 1: Payee Identification{Style.RESET_ALL}"
                        )

                        # Get payee info - using simplified signature
                        payee_info = self._get_payee(
                            transaction.description, force_process=force_process
                        )
                        transaction.payee_info = payee_info
                        stats["pass1_processed"] += 1

                        # After Pass 1
                        if resume_from_pass == 1:
                            self._commit_pass(1, transaction)

                    # Pass 2: Category assignment
                    if resume_from_pass <= 2:
                        logger.info(
                            f"{Fore.GREEN}▶ PASS 2: Category Assignment{Style.RESET_ALL}"
                        )

                        # Get category info
                        category_info = self._get_category(
                            transaction.description,
                            transaction.amount,
                            transaction.transaction_date,
                            force_process=force_process,
                            row_info=str(transaction),
                        )
                        transaction.category_info = category_info
                        stats["pass2_processed"] += 1

                        # After Pass 2
                        if resume_from_pass == 2:
                            self._commit_pass(2, transaction)

                    # Pass 3: Tax Classification
                    if resume_from_pass <= 3:
                        logger.info(
                            f"{Fore.GREEN}▶ PASS 3: Tax Classification{Style.RESET_ALL}"
                        )

                        # Get tax classification
                        tax_info = self._get_tax_classification(
                            transaction, force_process=force_process
                        )
                        transaction.tax_info = tax_info
                        stats["pass3_processed"] += 1

                        # After Pass 3
                        if resume_from_pass <= 3:
                            self._commit_pass(3, transaction)

                except Exception as e:
                    error_msg = (
                        f"[Row {row_number}] ❌ Error processing transaction: {str(e)}"
                    )
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    continue

            # Log final statistics
            logger.info(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")
            logger.info(f"{Fore.GREEN}▶ Processing Complete{Style.RESET_ALL}")
            logger.info(f"\nPass 1 Statistics:")
            logger.info(f"  • Processed: {stats['pass1_processed']}")
            logger.info(f"\nPass 2 Statistics:")
            logger.info(f"  • Processed: {stats['pass2_processed']}")
            logger.info(f"\nPass 3 Statistics:")
            logger.info(f"  • Processed: {stats['pass3_processed']}")
            if stats["errors"]:
                logger.info(f"\nErrors:")
                for error in stats["errors"]:
                    logger.info(f"  • {error}")
            logger.info(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")

        finally:
            # Always ensure we close the connection
            self._end_batch_processing()

        return stats

    def _check_previous_pass_completion(self, pass_number: int) -> bool:
        """Check if the previous pass was completed for all transactions."""
        with sqlite3.connect(self.profile_manager.db.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT COUNT(*) 
                FROM transaction_status 
                WHERE client_id = ? 
                AND pass_number = ? 
                AND status != 'completed'
                """,
                (self.client_id, pass_number),
            )
            incomplete_count = cursor.fetchone()[0]
            return incomplete_count == 0

    def _process_basic_categorization(
        self,
        transactions_df: pd.DataFrame,
        start_row: int,
        end_row: int,
        force_process: bool,
    ):
        """Process Pass 2: Basic category analysis."""
        print("\nPass 2: Basic Category Analysis...")
        for idx in range(start_row, end_row):
            transaction = transactions_df.iloc[idx]
            try:
                # Get existing payee info
                payee_info = self._get_existing_payee(transaction["transaction_id"])
                if not payee_info and not force_process:
                    continue

                # Determine basic category
                category_result = self._get_category(
                    transaction["description"],
                    payee_info["payee"] if payee_info else None,
                    payee_info["business_description"] if payee_info else None,
                    payee_info["general_category"] if payee_info else None,
                )

                # Save to database
                self.profile_manager.db.save_transaction_classification(
                    self.client_name,
                    transaction["transaction_id"],
                    {
                        "base_category": category_result.category,
                        "base_category_confidence": category_result.confidence,
                        "category_reasoning": category_result.reasoning,
                    },
                    "category",
                )

            except Exception as e:
                print(f"Error in Pass 2 for transaction {idx}: {str(e)}")
                self._update_status(transaction["transaction_id"], 2, "error", str(e))

    def _process_worksheet_assignment(
        self,
        transactions_df: pd.DataFrame,
        start_row: int,
        end_row: int,
        force_process: bool,
    ):
        """Process Pass 3: Worksheet assignment."""
        print("\nPass 3: Worksheet Assignment...")
        for idx in range(start_row, end_row):
            transaction = transactions_df.iloc[idx]
            try:
                # Get existing category info
                category_info = self._get_existing_category(
                    transaction["transaction_id"]
                )
                if not category_info and not force_process:
                    continue

                # Determine worksheet
                worksheet_result = self._determine_worksheet(
                    transaction, category_info["base_category"]
                )

                # Save to database
                self.profile_manager.db.save_transaction_classification(
                    self.client_name,
                    transaction["transaction_id"],
                    {
                        "worksheet": worksheet_result.worksheet,
                        "tax_category": worksheet_result.tax_category,
                        "tax_subcategory": worksheet_result.tax_subcategory,
                    },
                    "worksheet",
                )

            except Exception as e:
                print(f"Error in Pass 3 for transaction {idx}: {str(e)}")
                self._update_status(transaction["transaction_id"], 3, "error", str(e))

    def _analyze_search_results(
        self, transaction_desc: str, search_results: List[Dict], client_profile: Dict
    ) -> Dict:
        """Analyze search results to find the best match."""

        # Get industry keywords and vendor patterns from profile
        industry_keywords = client_profile.get("industry_keywords", {})
        vendor_patterns = client_profile.get("vendor_patterns", {})

        # Prepare prompt with business context
        prompt = f"""
        Transaction: {transaction_desc}
        Business Type: {client_profile.get('business_type', '')}
        Business Description: {client_profile.get('business_description', '')}
        Industry Keywords: {json.dumps(industry_keywords, indent=2)}
        Vendor Patterns: {json.dumps(vendor_patterns, indent=2)}

        Search Results:
        {json.dumps(search_results, indent=2)}

        Rules:
        1. Check if transaction matches any vendor patterns first
        2. Use industry keywords to assess relevance
        3. Consider business context for classification
        4. If no clear match, analyze general business relevance
        5. Provide confidence level and reasoning

        Return JSON with:
        {{
            "payee": "Standardized business name",
            "confidence": "high"|"medium"|"low",
            "business_description": "Brief description of the business",
            "general_category": "General business category",
            "reasoning": "Explanation of the match",
            "warning_flags": ["Any concerns or issues"],
            "industry_match_score": 0.0 to 1.0
        }}
        """

        # Get LLM analysis
        response = self._get_llm_response(prompt)

        try:
            result = json.loads(response)

            # Ensure all required fields are present
            required_fields = {
                "payee": str(transaction_desc),
                "confidence": "low",
                "business_description": "Could not determine business details",
                "general_category": "Unknown",
                "reasoning": "Failed to analyze results",
                "warning_flags": [],
                "industry_match_score": 0.0,
            }

            # Fill in any missing fields with defaults
            for field, default in required_fields.items():
                if field not in result:
                    result[field] = default
                    logger.warning(
                        f"Missing field '{field}' in analysis result, using default: {default}"
                    )

            # Adjust confidence based on industry match score
            industry_match = float(result.get("industry_match_score", 0))
            if industry_match > 0.8:
                result["confidence"] = "high"
            elif industry_match > 0.5:
                result["confidence"] = "medium"
            else:
                result["confidence"] = "low"

            # Log any warning flags
            if result.get("warning_flags"):
                for flag in result["warning_flags"]:
                    logger.warning(f"Warning flag: {flag}")

            return result

        except json.JSONDecodeError:
            logger.error("Failed to parse LLM response")
            return {
                "payee": str(transaction_desc),
                "confidence": "low",
                "business_description": "Could not determine business details",
                "general_category": "Unknown",
                "reasoning": "Failed to analyze results",
                "warning_flags": ["Failed to parse LLM response"],
                "industry_match_score": 0.0,
            }

    def _get_category(
        self,
        transaction_description: str,
        amount: float,
        date: str,
        payee: str = None,
        business_description: str = None,
        general_category: str = None,
        force_process: bool = False,
        row_info: str = "",
    ) -> CategoryResponse:
        """Get category for a transaction."""
        try:
            # First try to find a matching transaction
            match_data = self._find_matching_transaction(transaction_description)
            if match_data:
                logger.info(
                    f"{row_info} ✓ Using existing category: {match_data['category']}"
                )
                # Include all required fields for CategoryResponse
                return CategoryResponse(
                    category=match_data["category"],
                    confidence=match_data["category_confidence"],
                    notes=match_data.get(
                        "category_reasoning", "Using existing classification"
                    ),
                    expense_type=match_data.get(
                        "expense_type", "business"
                    ),  # Default to business if not found
                    business_percentage=match_data.get(
                        "business_percentage", 100
                    ),  # Default to 100% if not found
                )

            # Build the prompt
            prompt = self._build_category_prompt(
                transaction_description,
                payee or "Unknown",
                business_description,
                general_category,
            )

            # Get response from LLM
            response = self.client.chat.completions.create(
                model=self._get_model(),
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a transaction categorization assistant that provides JSON responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            result = json.loads(response.choices[0].message.content)

            # Ensure required fields are present
            if "expense_type" not in result:
                result["expense_type"] = "business"  # Default to business
            if "business_percentage" not in result:
                result["business_percentage"] = 100  # Default to 100%

            return CategoryResponse(**result)

        except Exception as e:
            logger.error(f"{row_info} ❌ Error in category assignment: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def process_single_row(
        self, transactions_df: pd.DataFrame, row_num: int, force_process: bool = False
    ) -> None:
        """Process a single row from the transactions DataFrame."""
        # Convert 1-based row number to 0-based index
        idx = row_num - 1
        if idx < 0 or idx >= len(transactions_df):
            raise ValueError(
                f"Row number {row_num} is out of range (1-{len(transactions_df)})"
            )

        # Process just this row using the main process_transactions method
        self.process_transactions(
            transactions_df, start_row=idx, end_row=idx + 1, force_process=force_process
        )

    def _build_payee_prompt(self, transaction_description: str) -> str:
        """Build a prompt for the LLM to identify the payee from a transaction description.

        Args:
            transaction_description: The raw transaction description to analyze.

        Returns:
            A formatted prompt string for the LLM.
        """
        prompt = (
            "Given this transaction description, please identify the business name (payee) "
            "and provide a brief description of what they do. Format your response as JSON with these fields:\n"
            "- payee: The standardized business name (e.g., 'Walmart' not 'WALMART #1234')\n"
            "- business_description: A brief description of what this business does\n"
            "- confidence: 'high' if very certain, 'medium' if somewhat certain, 'low' if uncertain\n"
            "- reasoning: Brief explanation of how you identified the payee\n\n"
            f"Transaction description: {transaction_description}\n\n"
            "Response in JSON:"
        )
        return prompt

    def _build_category_prompt(
        self,
        transaction_description: str,
        payee: str,
        business_description: str = None,
        general_category: str = None,
    ) -> str:
        """Build a prompt for the LLM to determine the transaction category.

        Args:
            transaction_description: The raw transaction description
            payee: The standardized payee name
            business_description: Optional description of the business
            general_category: Optional general category from payee identification

        Returns:
            A formatted prompt string for the LLM.
        """
        # Include business context and available categories
        prompt = (
            f"Given this transaction information:\n"
            f"Description: {transaction_description}\n"
            f"Payee: {payee}\n"
        )

        if business_description:
            prompt += f"Business Type: {business_description}\n"
        if general_category:
            prompt += f"General Category: {general_category}\n"

        # Add business context
        if self.business_context:
            prompt += f"\nBusiness Context:\n{self.business_context}\n"

        # Add available categories
        prompt += "\nAvailable Categories:\n"
        for category in self.standard_categories:
            prompt += f"- {category}\n"

        prompt += (
            "\nPlease categorize this transaction and provide your reasoning. "
            "Format your response as JSON with these fields:\n"
            "- category: The most appropriate category from the list above\n"
            "- confidence: 'high' if very certain, 'medium' if somewhat certain, 'low' if uncertain\n"
            "- notes: Brief explanation of why this category was chosen\n"
            "- expense_type: 'business' or 'personal'\n"
            "- business_percentage: Percentage that is business-related (0-100)\n\n"
            "Response in JSON:"
        )

        return prompt

    def _build_classification_prompt(
        self,
        transaction_description: str,
        payee: str,
        category: str,
        amount: float,
        date: str,
    ) -> str:
        """Build a prompt for the LLM to determine tax classification."""
        # Include transaction details and business context
        prompt = (
            f"Given this transaction information:\n"
            f"Description: {transaction_description}\n"
            f"Payee: {payee}\n"
            f"Category: {category}\n"
            f"Amount: ${amount:.2f}\n"
            f"Date: {date}\n"
        )

        # Add business context
        if self.business_context:
            prompt += f"\nBusiness Context:\n{self.business_context}\n"

        # Add numbered tax categories with descriptions
        prompt += "\nSelect ONE tax category by its number from this list:\n"
        for worksheet, categories in self.tax_categories.items():
            prompt += f"\n{worksheet} Categories:\n"
            if isinstance(categories, list):
                for category in categories:
                    # Get the ID from the database
                    tax_cat_query = (
                        "SELECT id FROM tax_categories WHERE name = ? AND worksheet = ?"
                    )
                    result = self.profile_manager.db.execute_query(
                        tax_cat_query, (category, worksheet)
                    )
                    if result:
                        category_id = result[0][0]
                        prompt += f"{category_id}. {category}\n"

        # Specify allowed worksheet values
        prompt += (
            "\nAllowed Worksheet Values (EXACT match required):\n"
            "- '6A': For general business expenses\n"
            "- 'Vehicle': For vehicle-related expenses\n"
            "- 'HomeOffice': For home office expenses\n"
        )

        prompt += (
            "\nCRITICAL RULES:\n"
            "1. tax_category_id MUST be a number from the list above\n"
            "2. worksheet MUST be exactly '6A', 'Vehicle', or 'HomeOffice'\n"
            "3. business_percentage must be 0-100\n"
            "\nFormat your response as JSON with these fields:\n"
            "- tax_category_id: The NUMBER of the chosen category from above\n"
            "- business_percentage: Percentage that is business-related (0-100)\n"
            "- worksheet: EXACT match from worksheet values above\n"
            "- confidence: 'high' if very certain, 'medium' if somewhat certain, 'low' if uncertain\n"
            "- reasoning: Brief explanation of the classification\n\n"
            "Response in JSON:"
        )

        return prompt

    def _determine_worksheet(
        self, transaction: pd.Series, base_category: str
    ) -> WorksheetAssignment:
        """Determine which worksheet a transaction belongs to."""
        try:
            # Default values
            worksheet = "6A"  # Default to main worksheet
            tax_category = base_category
            tax_subcategory = None
            line_number = "0"
            confidence = "medium"
            reasoning = "Default classification based on base category"

            # Check if it's a vehicle expense
            vehicle_keywords = [
                "gas",
                "fuel",
                "parking",
                "toll",
                "mileage",
                "car wash",
                "auto",
                "vehicle",
            ]
            if any(
                keyword in transaction["description"].lower()
                for keyword in vehicle_keywords
            ):
                worksheet = "Vehicle"
                tax_category = "Car and truck expenses"
                reasoning = "Vehicle-related expense based on description keywords"
                confidence = "high"

            # Check if it's a home office expense
            home_keywords = [
                "rent",
                "mortgage",
                "utilities",
                "internet",
                "phone",
                "office supplies",
            ]
            if any(
                keyword in transaction["description"].lower()
                for keyword in home_keywords
            ):
                worksheet = "HomeOffice"
                tax_category = base_category
                reasoning = "Home office expense based on description keywords"
                confidence = "high"

            # Ensure tax_category is never None
            if not tax_category:
                tax_category = "Other expenses"
                reasoning = "Defaulted to Other expenses due to missing classification"
                confidence = "low"

            return WorksheetAssignment(
                worksheet=worksheet,
                tax_category=tax_category,
                tax_subcategory=tax_subcategory,
                line_number=line_number,
                confidence=confidence,
                reasoning=reasoning,
            )

        except Exception as e:
            logger.error(f"Error in worksheet determination: {str(e)}")
            # Return safe default values on error
            return WorksheetAssignment(
                worksheet="6A",
                tax_category="Other expenses",
                tax_subcategory=None,
                line_number="0",
                confidence="low",
                reasoning=f"Error in classification: {str(e)}",
            )

    def create_test_sample(
        self,
        transactions: pd.DataFrame,
        sample_size: int = 10,
        include_keywords: List[str] = None,
    ) -> pd.DataFrame:
        """Create a test sample of transactions.

        Args:
            transactions: Full DataFrame of transactions
            sample_size: Number of transactions to include in sample (default 10)
            include_keywords: List of keywords to ensure are represented in the sample

        Returns:
            DataFrame containing the test sample
        """
        # Initialize sample indices
        sample_indices = set()

        # First, find transactions matching keywords if provided
        if include_keywords:
            for keyword in include_keywords:
                keyword_matches = transactions[
                    transactions["description"].str.contains(
                        keyword, case=False, na=False
                    )
                ]
                if not keyword_matches.empty:
                    # Add up to 2 matches for each keyword
                    matches_to_add = keyword_matches.head(2).index.tolist()
                    sample_indices.update(matches_to_add)

        # Then add random transactions until we reach sample_size
        remaining_size = sample_size - len(sample_indices)
        if remaining_size > 0:
            # Get indices not already in sample
            available_indices = set(range(len(transactions))) - sample_indices
            # Randomly select remaining transactions
            random_indices = pd.Series(list(available_indices)).sample(
                n=min(remaining_size, len(available_indices))
            )
            sample_indices.update(random_indices)

        # Create the sample DataFrame
        sample_df = transactions.iloc[sorted(list(sample_indices))].copy()

        # Log sample information
        logger.info(f"\n{Fore.GREEN}Test Sample Created:{Style.RESET_ALL}")
        logger.info(f"• Sample size: {len(sample_df)} transactions")
        if include_keywords:
            for keyword in include_keywords:
                count = sum(
                    sample_df["description"].str.contains(keyword, case=False, na=False)
                )
                logger.info(f"• Transactions with '{keyword}': {count}")

        return sample_df

    def run_test_sample(
        self,
        transactions: pd.DataFrame,
        sample_size: int = 10,
        include_keywords: List[str] = None,
        force_process: bool = True,
    ) -> None:
        """Run classification on a test sample of transactions.

        Args:
            transactions: Full DataFrame of transactions
            sample_size: Number of transactions to include in sample
            include_keywords: List of keywords to ensure are represented in the sample
            force_process: Whether to force processing even if transactions were previously processed
        """
        # Create test sample
        sample_df = self.create_test_sample(
            transactions, sample_size=sample_size, include_keywords=include_keywords
        )

        # Process the sample
        logger.info(f"\n{Fore.GREEN}Processing Test Sample{Style.RESET_ALL}")
        stats = self.process_transactions(
            sample_df,
            force_process=force_process,
            batch_size=5,  # Smaller batch size for test sample
        )

        return sample_df, stats

    def _get_tax_classification(
        self, transaction: TransactionInfo, force_process: bool = False
    ) -> TaxInfo:
        """Get tax classification for a transaction."""
        try:
            # First try to find a matching transaction
            match_data = self._find_matching_transaction(transaction.description)
            if match_data and not force_process:
                logger.info(f"✓ Using existing classification from match")
                return TaxInfo(
                    tax_category_id=match_data["tax_category_id"],
                    tax_category=match_data["tax_category"],
                    business_percentage=match_data["business_percentage"],
                    worksheet=match_data["worksheet"] or "6A",  # Default to 6A if null
                    confidence=match_data["classification_confidence"]
                    or "medium",  # Default to medium if null
                    reasoning="Using existing classification from matching transaction",
                )

            # If no match or force_process, get the tax category ID from the category name
            if transaction.category_info:
                # First try to find exact match
                tax_cat_query = (
                    "SELECT id, name FROM tax_categories WHERE LOWER(name) = LOWER(?)"
                )
                tax_cat_result = self.profile_manager.db.execute_query(
                    tax_cat_query, (transaction.category_info.category,)
                )

                if tax_cat_result:
                    row = tax_cat_result[0]
                    logger.info(f"✓ Found tax category match: {row[1]} (ID: {row[0]})")
                    return TaxInfo(
                        tax_category_id=row[0],
                        tax_category=row[1],
                        business_percentage=transaction.category_info.business_percentage,
                        worksheet="6A",  # Default to 6A for now
                        confidence=transaction.category_info.confidence,
                        reasoning=f"Mapped from category: {transaction.category_info.category}",
                    )
                else:
                    logger.warning(
                        f"No exact tax category match found for: {transaction.category_info.category}"
                    )

            # If we get here, we need to use AI to classify
            prompt = self._build_classification_prompt(
                transaction.description,
                transaction.payee_info.payee if transaction.payee_info else "Unknown",
                (
                    transaction.category_info.category
                    if transaction.category_info
                    else "Unknown"
                ),
                transaction.amount,
                transaction.transaction_date,
            )

            # Get response from OpenAI
            response = self.client.chat.completions.create(
                model=self._get_model(),
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a transaction classification assistant that provides JSON responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            result = json.loads(response.choices[0].message.content)
            classification = ClassificationResponse(**result)

            # Ensure confidence is one of the allowed values
            if classification.confidence not in ["high", "medium", "low"]:
                classification.confidence = "medium"  # Default to medium if invalid

            # Get tax_category_id from the name
            tax_cat_query = "SELECT id, name FROM tax_categories WHERE id = ?"
            tax_cat_result = self.profile_manager.db.execute_query(
                tax_cat_query, (classification.tax_category_id,)
            )

            if not tax_cat_result:
                logger.error(
                    f"Tax category ID not found in database: {classification.tax_category_id}"
                )
                # Try to find a similar category
                all_categories = self.profile_manager.db.execute_query(
                    "SELECT id, name FROM tax_categories"
                )
                if all_categories:
                    logger.info("Available tax categories:")
                    for cat in all_categories:
                        logger.info(f"  ID {cat[0]}: {cat[1]}")
                return TaxInfo(
                    tax_category_id=0,  # Default/unknown ID
                    tax_category="Unknown",
                    business_percentage=0,
                    worksheet="6A",  # Default to 6A
                    confidence="low",  # Default to low confidence
                    reasoning="Tax category not found in database",
                )

            row = tax_cat_result[0]
            logger.info(f"✓ Using tax category: {row[1]} (ID: {row[0]})")
            return TaxInfo(
                tax_category_id=row[0],
                tax_category=row[1],
                business_percentage=classification.business_percentage,
                worksheet=classification.worksheet
                or "6A",  # Default to 6A if not specified
                confidence=classification.confidence,
                reasoning=classification.reasoning,
            )

        except Exception as e:
            logger.error(
                f"Error getting tax classification for transaction {transaction.transaction_id}: {str(e)}"
            )
            return TaxInfo(
                tax_category_id=0,  # Default/unknown ID
                tax_category="Unknown",
                business_percentage=0,
                worksheet="6A",  # Default to 6A
                confidence="low",  # Default to low confidence
                reasoning=f"Error during classification: {str(e)}",
            )
