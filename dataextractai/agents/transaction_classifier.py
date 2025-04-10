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
from typing import Dict, List, Optional, Any, Tuple
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
import time
from collections import defaultdict
from pydantic import ValidationError as PydanticValidationError
import hashlib
from ..utils.constants import CATEGORY_MAPPING, CATEGORY_ID_TO_NAME, ALLOWED_WORKSHEETS
import uuid

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
class TaxInfo:
    """Tax classification information for a transaction."""

    tax_category_id: int  # Changed from tax_category: str
    tax_category: str  # Keep this for display/logging purposes
    business_percentage: int
    worksheet: str
    confidence: str
    reasoning: str
    tax_implications: str = ""

    def as_dict(self, prefix: str = "") -> Dict[str, Any]:
        """Convert to dictionary with optional prefix for key names."""
        prefix = f"{prefix}_" if prefix else ""
        return {
            f"{prefix}tax_category_id": self.tax_category_id,
            f"{prefix}tax_category": self.tax_category,
            f"{prefix}business_percentage": self.business_percentage,
            f"{prefix}worksheet": self.worksheet,
            f"{prefix}confidence": self.confidence,
            f"{prefix}reasoning": self.reasoning,
            f"{prefix}tax_implications": self.tax_implications,
        }


@dataclass
class TransactionInfo:
    """Class to hold transaction information during processing."""

    transaction_id: str
    description: str
    amount: float
    transaction_date: str
    payee_info: Optional[PayeeResponse] = None
    category_info: Optional[CategoryResponse] = None
    tax_info: Optional[TaxInfo] = None

    def __str__(self):
        return f"[Transaction {self.transaction_id}]"


class TransactionClassifier:
    """Classify transactions with caching."""

    # Define allowed worksheets as a class constant
    ALLOWED_WORKSHEETS = ALLOWED_WORKSHEETS

    def __init__(self, client_name: str):
        """Initialize the transaction classifier."""
        self.client = OpenAI()
        self.client_name = client_name
        self.db = ClientDB()
        self.client_id = self.db.get_client_id(client_name)
        if not self.client_id:
            raise ValueError(f"Failed to get or create client ID for '{client_name}'.")

        self.business_profile = self.db.load_profile(client_name)
        if not self.business_profile:
            logger.warning(
                f"No business profile found for client '{client_name}'. Context will be limited."
            )

        self._persistent_conn = None
        self._transaction_active = False

        self.business_context = self._get_business_context()

        self.business_categories_by_id: Dict[int, Tuple[str, str]] = {}
        self.business_category_id_by_name_ws: Dict[Tuple[str, str], int] = {}
        self.personal_category_id: Optional[int] = None
        self._load_category_mappings()

        self.client_categories = {}

    def _load_category_mappings(self):
        """Load tax category mappings from the database."""
        logger.info("Loading tax category mappings from database...")
        all_categories = self.db.execute_query(
            "SELECT id, name, worksheet, is_personal FROM tax_categories ORDER BY id"
        )

        found_personal = False
        for cat_id, name, worksheet, is_personal in all_categories:
            if is_personal:
                if name == "Personal Expense":
                    self.personal_category_id = cat_id
                    logger.info(f"Found Personal Expense category with ID: {cat_id}")
                    found_personal = True
                # else: ignore other personal categories if any
            else:
                # Business category
                self.business_categories_by_id[cat_id] = (name, worksheet)
                self.business_category_id_by_name_ws[(name, worksheet)] = cat_id

        if not found_personal:
            logger.error(
                "CRITICAL: 'Personal Expense' category not found in the database!"
            )
            # Handle this error appropriately - maybe raise an exception?

        logger.info(
            f"Loaded {len(self.business_categories_by_id)} business category mappings."
        )
        if not self.business_categories_by_id:
            logger.warning("No business categories found in the database!")

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

        # Add any custom categories (consider if these are relevant for context)
        # if self.business_profile.get("custom_categories"):
        #     categories = self.business_profile["custom_categories"]
        #     if isinstance(categories, list):
        #         context_parts.append(f"Custom Categories: {', '.join(categories)}")

        # TODO: Add custom business rules from profile if available and relevant

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
            result = self.db.execute_query(query, (self.client_id, description))

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
                    result = self.db.execute_query(query, (self.client_id, pattern))

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
        # When force_process is True, skip all matching and go directly to AI
        if force_process:
            logger.info(f"🧠 FORCED AI payee identification for: {description}")
        else:
            # Only check for matches if not forcing LLM processing
            match_data = self._find_matching_transaction(description)
            if match_data:
                logger.info(
                    f"✓ Using existing payee from matching transaction: {match_data['payee']}"
                )
                return PayeeResponse(
                    payee=match_data["payee"],
                    confidence="high",
                    reasoning=f"Using existing payee from matching transaction",
                    business_description=match_data.get("business_description", ""),
                    general_category=match_data.get("general_category", ""),
                )

        # If force_process=True or no match found, use LLM
        logger.info(f"🧠 Using AI for payee identification")
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
        logger.info(f"✓ AI Payee Identified: {result.get('payee', 'Unknown')}")
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
            self._persistent_conn = sqlite3.connect(self.db.db_path)
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
                self.db.execute_query(
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
                self.db.execute_query(
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
                # CRITICAL: Ensure personal expenses always go to the Personal worksheet
                # Check both methods to identify personal expenses
                is_personal_by_id = (
                    transaction.tax_info.tax_category_id == self.personal_category_id
                )
                is_personal_by_type = (
                    transaction.category_info
                    and transaction.category_info.expense_type == "personal"
                )
                is_personal = is_personal_by_id or is_personal_by_type

                logger.info(
                    f"[ID:{transaction.transaction_id}] Personal check: by_id={is_personal_by_id}, by_type={is_personal_by_type}, final={is_personal}"
                )

                if is_personal:
                    # Force the worksheet to be Personal
                    worksheet = "Personal"
                    logger.info(
                        f"✓ Setting worksheet to 'Personal' for personal expense (ID: {transaction.transaction_id})"
                    )
                else:
                    # For business expenses, validate the worksheet
                    worksheet = transaction.tax_info.worksheet

                    # Handle various data type issues
                    if isinstance(worksheet, list):
                        logger.warning(
                            f"Worksheet is still a list in commit: {worksheet}, using first value or '6A'"
                        )
                        worksheet = (
                            worksheet[0]
                            if worksheet and isinstance(worksheet[0], str)
                            else "6A"
                        )

                    # Final validation for business expenses - ensure worksheet is one of the allowed values
                    if worksheet not in self.ALLOWED_WORKSHEETS:
                        logger.warning(
                            f"Invalid worksheet '{worksheet}' at commit time for business expense. Using '6A'."
                        )
                        worksheet = "6A"
                        logger.info("Defaulted to '6A' worksheet")

                # Use the validated worksheet value
                self.db.execute_query(
                    """UPDATE transaction_classifications 
                       SET tax_category_id = ?, business_percentage = ?, 
                           worksheet = ?, classification_confidence = ?,
                           classification_reasoning = ?, expense_type = ?
                       WHERE transaction_id = ?""",
                    (
                        transaction.tax_info.tax_category_id,  # Using ID instead of name
                        (
                            0
                            if is_personal
                            else transaction.tax_info.business_percentage
                        ),  # Force 0% for personal
                        worksheet,  # Use the validated worksheet value
                        transaction.tax_info.confidence,
                        transaction.tax_info.reasoning,
                        (
                            "personal" if is_personal else "business"
                        ),  # Explicitly set expense_type
                        transaction.transaction_id,
                    ),
                )
                # Get tax category name from ID for logging
                tax_cat_query = "SELECT name FROM tax_categories WHERE id = ?"
                tax_cat_result = self.db.execute_query(
                    tax_cat_query, (transaction.tax_info.tax_category_id,)
                )
                tax_category_name = (
                    tax_cat_result[0][0] if tax_cat_result else "Unknown"
                )

                logger.info(
                    f"✓ Pass 3 complete: {tax_category_name} ({transaction.tax_info.confidence}) with worksheet: {worksheet}, expense_type: {'personal' if is_personal else 'business'}"
                )

            # Use the connection from the persistent connection pool
            if self._persistent_conn:
                self._persistent_conn.commit()
            else:
                # If no persistent connection, commit using the profile manager's connection
                self.db.execute_query("COMMIT")

        except Exception as e:
            logger.error(f"Error committing pass {pass_num}: {str(e)}")
            if self._persistent_conn:
                self._persistent_conn.rollback()
            raise

    def _load_client_categories(self) -> List[str]:
        """Load client-specific categories from the database."""
        with sqlite3.connect(self.db.db_path) as conn:
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

        # Clean the description to remove common noise
        clean_desc = re.sub(r"[^A-Za-z0-9\s]", "", description.upper())
        clean_desc = re.sub(r"\s+", " ", clean_desc).strip()

        # Build key parts
        key_parts = [clean_desc]  # Use more of the description for uniqueness
        if payee:
            key_parts.append(payee.upper())
        if category:
            key_parts.append(category.upper())
        if pass_type:
            key_parts.append(pass_type.upper())

        # Join with pipe delimiter for consistency
        result = "|".join(key_parts)
        # Generate a reproducible hash to shorten long keys
        if len(result) > 200:
            result = hashlib.md5(result.encode()).hexdigest()

        return result

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

            result = self.db.execute_query(query, params)
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

            self.db.execute_query(
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
        transactions_df: pd.DataFrame,
        process_passes: Tuple[bool, bool, bool] = (True, True, True),
        force_process: bool = False,
        batch_size: int = 50,
        start_row: int = 0,
        end_row: int = None,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Process transactions through multiple classification passes."""
        try:
            # Start batch processing with persistent connection
            self._start_batch_processing()

            if not isinstance(transactions_df, pd.DataFrame):
                raise ValueError("transactions must be a pandas DataFrame")

            # Respect row limits
            if end_row is None:
                end_row = len(transactions_df)

            # Slice the DataFrame to the requested range
            transactions_to_process = transactions_df.iloc[start_row:end_row].copy()

            stats = {
                "total_transactions": len(transactions_to_process),
                "processed": 0,
                "pass1_processed": 0,
                "pass1_completed": 0,
                "pass1_errors": 0,
                "pass1_skipped": 0,
                "pass1_time": 0,
                "pass2_processed": 0,
                "pass2_completed": 0,
                "pass2_errors": 0,
                "pass2_skipped": 0,
                "pass2_time": 0,
                "pass3_processed": 0,
                "pass3_completed": 0,
                "pass3_errors": 0,
                "pass3_skipped": 0,
                "pass3_time": 0,
            }
            status_updates = defaultdict(dict)
            processed_rows = []

            total_batches = (
                len(transactions_to_process) + batch_size - 1
            ) // batch_size

            for batch_num, i in enumerate(
                range(0, len(transactions_to_process), batch_size)
            ):
                batch_df = transactions_to_process.iloc[i : i + batch_size]
                logger.info(f"--- Processing Batch {batch_num + 1}/{total_batches} ---")

                for index, row in batch_df.iterrows():
                    transaction_id = str(row["transaction_id"])
                    row_info = f"[ID: {transaction_id}]"
                    actual_row_num = index + 1  # For user-friendly display (1-indexed)
                    logger.info(
                        f"Processing transaction {actual_row_num} (ID: {transaction_id}) - {stats['processed'] + 1}/{len(transactions_to_process)}"
                    )
                    stats["processed"] += 1

                    # Get current status
                    status = (
                        self.db.get_transaction_status(self.client_name, transaction_id)
                        or {}
                    )
                    status_updates[transaction_id][
                        "client_id"
                    ] = self.client_id  # Ensure client_id is set

                    transaction = TransactionInfo(
                        transaction_id=transaction_id,
                        description=row["description"],
                        amount=row["amount"],
                        transaction_date=str(row["transaction_date"]),
                    )

                    # --- Pass 1: Payee Identification --- #
                    if process_passes[0] and (
                        force_process
                        or status.get("pass_1_status", "pending") != "completed"
                    ):
                        logger.info(
                            f"🔄 Starting Pass 1: Payee Identification... {row_info}"
                        )
                        start_time_pass1 = time.time()
                        try:
                            transaction.payee_info = self._get_payee(
                                row["description"], force_process=force_process
                            )
                            self._commit_pass(1, transaction)
                            stats["pass1_completed"] += 1
                            status_updates[transaction_id][
                                "pass_1_status"
                            ] = "completed"
                            status_updates[transaction_id]["pass_1_error"] = None
                            status_updates[transaction_id][
                                "pass_1_processed_at"
                            ] = datetime.now().isoformat()
                        except Exception as e_p1:
                            logger.error(
                                f"❌ Error during Pass 1 for transaction {transaction_id}: {str(e_p1)}"
                            )
                            logger.error(traceback.format_exc())
                            stats["pass1_errors"] += 1
                            status_updates[transaction_id]["pass_1_status"] = "error"
                            status_updates[transaction_id]["pass_1_error"] = str(e_p1)
                            status_updates[transaction_id][
                                "pass_1_processed_at"
                            ] = datetime.now().isoformat()
                            # Optionally assign default PayeeInfo on error
                            if not transaction.payee_info:
                                transaction.payee_info = PayeeResponse(
                                    payee="Error",
                                    confidence="low",
                                    reasoning=f"Pass 1 Error: {str(e_p1)}",
                                )

                        stats["pass1_processed"] += 1
                        stats["pass1_time"] += time.time() - start_time_pass1
                    else:
                        logger.info(
                            f"⏭️ Skipping Pass 1 (already completed or not requested). {row_info}"
                        )
                        stats["pass1_skipped"] += 1
                        # Load existing Pass 1 data if needed for subsequent passes
                        if not transaction.payee_info:
                            existing_class = self.db.get_transaction_classification(
                                transaction_id
                            )
                            if existing_class and existing_class.get("payee"):
                                transaction.payee_info = PayeeResponse(
                                    payee=existing_class["payee"],
                                    confidence=existing_class.get(
                                        "payee_confidence", "medium"
                                    ),
                                    reasoning=existing_class.get(
                                        "payee_reasoning", "Loaded existing"
                                    ),
                                )

                    # --- Pass 2: Category Assignment --- #
                    if process_passes[1] and (
                        force_process
                        or status.get("pass_2_status", "pending") != "completed"
                    ):
                        logger.info(
                            f"🔄 Starting Pass 2: Category Assignment... {row_info}"
                        )
                        start_time_pass2 = time.time()
                        try:
                            transaction.category_info = self._get_category(
                                description=row["description"],
                                amount=row["amount"],
                                date=str(row["transaction_date"]),
                                force_process=force_process,
                                row_info=row_info,
                            )
                            self._commit_pass(2, transaction)
                            stats["pass2_completed"] += 1
                            status_updates[transaction_id][
                                "pass_2_status"
                            ] = "completed"
                            status_updates[transaction_id]["pass_2_error"] = None
                            status_updates[transaction_id][
                                "pass_2_processed_at"
                            ] = datetime.now().isoformat()
                        except Exception as e_p2:
                            logger.error(
                                f"❌ Error during Pass 2 for transaction {transaction_id}: {str(e_p2)}"
                            )
                            logger.error(traceback.format_exc())
                            stats["pass2_errors"] += 1
                            status_updates[transaction_id]["pass_2_status"] = "error"
                            status_updates[transaction_id]["pass_2_error"] = str(e_p2)
                            status_updates[transaction_id][
                                "pass_2_processed_at"
                            ] = datetime.now().isoformat()
                            # Optionally assign default CategoryInfo on error
                            if not transaction.category_info:
                                transaction.category_info = CategoryResponse(
                                    category="Error",
                                    expense_type="unknown",
                                    business_percentage=-1,
                                    notes=f"Pass 2 Error: {str(e_p2)}",
                                    confidence="low",
                                    detailed_context="",
                                )

                        stats["pass2_processed"] += 1
                        stats["pass2_time"] += time.time() - start_time_pass2
                    else:
                        logger.info(
                            f"⏭️ Skipping Pass 2 (already completed or not requested). {row_info}"
                        )
                        stats["pass2_skipped"] += 1
                        # Load existing Pass 2 data if needed for subsequent passes
                        if not transaction.category_info:
                            existing_class = self.db.get_transaction_classification(
                                transaction_id
                            )
                            if existing_class and existing_class.get("category"):
                                transaction.category_info = CategoryResponse(
                                    category=existing_class["category"],
                                    expense_type=existing_class.get(
                                        "expense_type", "unknown"
                                    ),
                                    business_percentage=existing_class.get(
                                        "business_percentage", -1
                                    ),
                                    notes=existing_class.get(
                                        "category_reasoning", "Loaded existing"
                                    ),
                                    confidence=existing_class.get(
                                        "category_confidence", "medium"
                                    ),
                                    detailed_context=existing_class.get(
                                        "business_context", ""
                                    ),
                                )

                    # --- Pass 3: Tax Classification --- #
                    if process_passes[2] and (
                        force_process
                        or status.get("pass_3_status", "pending") != "completed"
                    ):
                        logger.info(
                            f"🔄 Starting Pass 3: Tax Classification... {row_info}"
                        )
                        start_time_pass3 = time.time()
                        pass3_processed = False
                        pass3_error = None
                        try:
                            # ===>>> LOGIC SPLIT START <<<===
                            # Check if Pass 2 determined it was personal
                            if (
                                transaction.category_info
                                and transaction.category_info.expense_type == "personal"
                            ):
                                logger.info(
                                    f"✓ Skipping Pass 3 AI: Marked as Personal in Pass 2. {row_info}"
                                )
                                # Ensure personal_category_id was loaded
                                if self.personal_category_id is None:
                                    logger.error(
                                        "CRITICAL: Personal Category ID not loaded! Cannot assign personal expense."
                                    )
                                    pass3_error = "Personal Category ID not loaded"
                                    # Assign error TaxInfo
                                    transaction.tax_info = TaxInfo(
                                        tax_category_id=0,
                                        tax_category="Error",
                                        business_percentage=0,
                                        worksheet="Unknown",
                                        confidence="low",
                                        reasoning=pass3_error,
                                    )
                                else:
                                    # Assign Personal TaxInfo directly
                                    transaction.tax_info = TaxInfo(
                                        tax_category_id=self.personal_category_id,
                                        tax_category="Personal Expense",
                                        business_percentage=0,
                                        worksheet="Personal",
                                        confidence="high",  # High confidence as it was determined in Pass 2
                                        reasoning="Classified as Personal based on Pass 2 (Category Assignment)",
                                    )
                                pass3_processed = (
                                    True  # Mark as processed for status update
                                )
                            elif not transaction.category_info:
                                # Handle case where Pass 2 failed or was skipped but Pass 3 is requested
                                logger.warning(
                                    f"⚠️ Pass 2 info missing, cannot reliably determine Personal/Business for Pass 3. Skipping tax classification. {row_info}"
                                )
                                pass3_error = "Pass 2 info missing"
                                transaction.tax_info = TaxInfo(
                                    tax_category_id=0,
                                    tax_category="Skipped",
                                    business_percentage=0,
                                    worksheet="Unknown",
                                    confidence="low",
                                    reasoning=pass3_error,
                                )
                                # Don't set pass3_processed = True, let status remain pending or error if it was already error
                                status_updates[transaction_id][
                                    "pass_3_status"
                                ] = "skipped"
                                status_updates[transaction_id][
                                    "pass_3_error"
                                ] = pass3_error
                                status_updates[transaction_id][
                                    "pass_3_processed_at"
                                ] = datetime.now().isoformat()

                            else:
                                # Proceed with business tax classification (AI or matching)
                                logger.debug(
                                    f"Proceeding with Pass 3 Business Tax Classification. {row_info}"
                                )
                                transaction.tax_info = self._get_tax_classification(
                                    transaction, force_process=force_process
                                )
                                pass3_processed = True  # Mark as processed
                            # ===>>> LOGIC SPLIT END <<<===

                            # Commit result after successful processing or direct assignment
                            if pass3_processed:
                                self._commit_pass(3, transaction)
                                stats["pass3_completed"] += 1
                                status_updates[transaction_id][
                                    "pass_3_status"
                                ] = "completed"
                                status_updates[transaction_id]["pass_3_error"] = None
                                status_updates[transaction_id][
                                    "pass_3_processed_at"
                                ] = datetime.now().isoformat()

                        except Exception as e_p3:
                            logger.error(
                                f"❌ Error during Pass 3 for transaction {transaction_id}: {str(e_p3)}"
                            )
                            logger.error(traceback.format_exc())
                            stats["pass3_errors"] += 1
                            pass3_error = str(e_p3)
                            status_updates[transaction_id]["pass_3_status"] = "error"
                            status_updates[transaction_id]["pass_3_error"] = pass3_error
                            status_updates[transaction_id][
                                "pass_3_processed_at"
                            ] = datetime.now().isoformat()
                            # Optionally, assign a default error TaxInfo
                            if not transaction.tax_info:
                                transaction.tax_info = TaxInfo(
                                    tax_category_id=0,
                                    tax_category="Error",
                                    business_percentage=0,
                                    worksheet="Unknown",
                                    confidence="low",
                                    reasoning=f"Pass 3 Error: {pass3_error}",
                                )

                        stats[
                            "pass3_processed"
                        ] += 1  # Count even if skipped due to missing Pass 2
                        stats["pass3_time"] += time.time() - start_time_pass3
                    else:
                        logger.info(
                            f"⏭️ Skipping Pass 3 (already completed or not requested). {row_info}"
                        )
                        stats["pass3_skipped"] += 1
                        # Load existing Pass 3 data if needed
                        if not transaction.tax_info:
                            existing_class = self.db.get_transaction_classification(
                                transaction_id
                            )
                            if (
                                existing_class
                                and existing_class.get("tax_category_id") is not None
                            ):
                                # Need category name and worksheet from ID mapping
                                cat_id = existing_class["tax_category_id"]
                                if cat_id == self.personal_category_id:
                                    cat_name = "Personal Expense"
                                    ws_name = "Personal"
                                elif cat_id in self.business_categories_by_id:
                                    cat_name, ws_name = self.business_categories_by_id[
                                        cat_id
                                    ]
                                else:
                                    cat_name = "Unknown Category (Loaded)"
                                    ws_name = "Unknown"

                                transaction.tax_info = TaxInfo(
                                    tax_category_id=cat_id,
                                    tax_category=cat_name,
                                    business_percentage=existing_class.get(
                                        "business_percentage", 0
                                    ),
                                    worksheet=existing_class.get("worksheet", ws_name),
                                    confidence=existing_class.get(
                                        "classification_confidence", "medium"
                                    ),
                                    reasoning=existing_class.get(
                                        "classification_reasoning", "Loaded existing"
                                    ),
                                )

                    # Append results (ensure all relevant fields are populated)
                    processed_row_data = row.to_dict()
                    if transaction.payee_info:
                        processed_row_data.update(
                            transaction.payee_info.as_dict("payee")
                        )
                    if transaction.category_info:
                        processed_row_data.update(
                            transaction.category_info.as_dict("category")
                        )
                    if transaction.tax_info:
                        # Log the field names for debugging
                        tax_fields = transaction.tax_info.as_dict("tax")
                        logger.debug(f"Tax info fields: {list(tax_fields.keys())}")
                        processed_row_data.update(tax_fields)

                        # Make sure we're using names, not IDs for display
                        # If tax_category is an ID, get the readable name from the business_categories_by_id mapping
                        if isinstance(processed_row_data.get("tax_category_id"), int):
                            tax_id = processed_row_data.get("tax_category_id")

                            # Handle Personal Expense specially
                            if tax_id == self.personal_category_id:
                                processed_row_data["tax_category"] = "Personal Expense"
                            # Otherwise look up business category name
                            elif tax_id in self.business_categories_by_id:
                                processed_row_data["tax_category"] = (
                                    self.business_categories_by_id[tax_id][0]
                                )
                            else:
                                processed_row_data["tax_category"] = (
                                    f"Unknown Category ({tax_id})"
                                )

                        # Check for personal expense
                        is_personal = (
                            transaction.category_info
                            and transaction.category_info.expense_type == "personal"
                        )

                        # CRITICAL: Ensure Personal expenses always go to Personal worksheet
                        if is_personal:
                            logger.info(
                                f"Transaction ID {transaction.transaction_id} is a personal expense, forcing Personal worksheet assignment"
                            )
                            # Try both possible field names
                            if processed_row_data.get("tax_worksheet") != "Personal":
                                processed_row_data["tax_worksheet"] = "Personal"
                                logger.warning(f"⚠️ Corrected tax_worksheet to Personal")
                            if processed_row_data.get("worksheet") != "Personal":
                                processed_row_data["worksheet"] = "Personal"
                                logger.warning(f"⚠️ Corrected worksheet to Personal")

                            # Also ensure transaction.tax_info reflects this change
                            if (
                                transaction.tax_info
                                and transaction.tax_info.worksheet != "Personal"
                            ):
                                transaction.tax_info.worksheet = "Personal"
                                logger.warning(
                                    f"⚠️ Corrected transaction.tax_info.worksheet to Personal"
                                )

                                # Re-commit the transaction with the corrected worksheet
                                self._commit_pass(3, transaction)
                                logger.info(
                                    f"✓ Re-committed Pass 3 with corrected Personal worksheet"
                                )

                            # Try both possible business percentage field names
                            if (
                                processed_row_data.get("tax_business_percentage", 100)
                                != 0
                            ):
                                processed_row_data["tax_business_percentage"] = 0
                                logger.warning(
                                    f"⚠️ Corrected tax_business_percentage to 0%"
                                )
                            if processed_row_data.get("business_percentage", 100) != 0:
                                processed_row_data["business_percentage"] = 0
                                logger.warning(f"⚠️ Corrected business_percentage to 0%")

                    processed_rows.append(processed_row_data)

                # This block should be aligned with the 'for index, row...' loop start
                logger.info(
                    f"Updating status for {len(status_updates)} transactions in batch {batch_num + 1}..."
                )
                for tx_id, updates in status_updates.items():
                    self.db.update_transaction_status(tx_id, updates)
                status_updates.clear()  # Clear updates for next batch

            logger.info("--- Batch processing complete ---")

        except Exception as e:
            logger.error(f"Unhandled error during batch processing: {str(e)}")
            logger.error(traceback.format_exc())
            # Ensure transaction rollback if active
            # self._rollback_batch_processing()
            raise  # Re-raise the exception
        finally:
            # Ensure connection is closed and transaction ended
            self._end_batch_processing()

        # Final DataFrame construction
        processed_df = pd.DataFrame(processed_rows)
        # Ensure correct column order or select specific columns if needed

        logger.info(f"Transaction processing finished. Stats: {stats}")
        return processed_df, stats

    def _check_previous_pass_completion(self, pass_number: int) -> bool:
        """Check if the previous pass was completed for all transactions."""
        with sqlite3.connect(self.db.db_path) as conn:
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
                    transaction["amount"],
                    transaction["transaction_date"],
                    force_process,
                    f"[ID: {transaction['transaction_id']}]",
                )

                # Save to database
                self.db.save_transaction_classification(
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
        self, df: pd.DataFrame, rows_to_process: List[int], force_process: bool = False
    ) -> pd.DataFrame:
        """Process worksheet assignments for transactions.

        Args:
            df: DataFrame with transactions
            rows_to_process: List of row indices to process
            force_process: Whether to force processing even if already processed

        Returns:
            DataFrame with updated worksheet values
        """
        # Initialize counters for logging
        count_processed = 0
        count_already_processed = 0

        # Process each transaction based on its indices
        for idx in rows_to_process:
            try:
                # Get row data for this transaction
                row = df.iloc[idx]
                transaction_id = row.get("transaction_id", f"row_{idx}")

                # Skip if already processed and not forcing
                if not force_process and pd.notna(row.get("worksheet")):
                    count_already_processed += 1
                    continue

                # Get existing category information
                expense_type = row.get("expense_type", None)

                # Determine worksheet
                worksheet = self._determine_worksheet(row)

                # CRITICAL SAFETY CHECK: Personal expenses MUST NEVER go to 6A
                if expense_type == "personal" and worksheet == "6A":
                    logger.warning(
                        f"🚨 CRITICAL SAFETY: Prevented personal expense ID {transaction_id} "
                        f"from being assigned to 6A worksheet. Forcing 'Personal' worksheet."
                    )
                    worksheet = "Personal"

                # Save the worksheet assignment to the dataframe
                df.at[idx, "worksheet"] = worksheet
                count_processed += 1

                # Also save to database for future reference if we have a transaction ID
                transaction_id = row.get("transaction_id")
                if transaction_id:
                    self._save_classification_to_db(
                        transaction_id=transaction_id,
                        tax_category_id=row.get("tax_category_id"),
                        tax_category=row.get("tax_category"),
                        business_percentage=row.get("business_percentage", 0),
                        worksheet=worksheet,
                        confidence=row.get("classification_confidence", "medium"),
                    )

            except Exception as e:
                transaction_id = df.iloc[idx].get("transaction_id", f"row_{idx}")
                logger.error(f"Error processing worksheet for ID {transaction_id}: {e}")
                continue

        # Log processing statistics
        logger.info(f"Processed worksheet assignment for {count_processed} rows")
        if count_already_processed > 0:
            logger.info(f"Skipped {count_already_processed} rows already processed")

        return df

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
        description: str,
        amount: float,
        date: str,
        force_process: bool = False,
        row_info: str = "",
    ) -> CategoryResponse:
        """Assign a category to the transaction using AI."""
        # When force_process is True, skip all matching and caching and go directly to AI
        if force_process:
            logger.info(f"🧠 FORCED AI categorization for {row_info}")
        else:
            # Only try to find matches if we're not forcing AI processing
            match_data = self._find_matching_transaction(description)
            if match_data:
                logger.info(f"✅ Found exact match for description... {row_info}")
                # Use existing category if available and seems valid
                if match_data.get("category"):
                    logger.info(f"✓ Using existing category: {match_data['category']}")
                    return CategoryResponse(
                        category=match_data["category"],
                        expense_type=match_data.get("expense_type", "business"),
                        business_percentage=match_data.get("business_percentage", 100),
                        notes=match_data.get(
                            "category_reasoning", "Using matched category"
                        ),
                        confidence=match_data.get("category_confidence", "high"),
                        detailed_context=match_data.get("business_context", ""),
                    )
                else:
                    logger.warning(
                        f"⚠️ Match found, but no category available. Proceeding with AI."
                    )

        # Proceed with AI classification if no match or if force_process is True
        logger.info(f"🧠 Using AI for category assignment... {row_info}")
        prompt = self._build_category_prompt(description, amount, date)
        response = self.client.chat.completions.create(
            model=self._get_model(),
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "You are a transaction categorization assistant providing JSON responses.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        result = json.loads(response.choices[0].message.content)
        category_response = CategoryResponse(**result)
        logger.info(
            f"✓ AI Category Assigned: {category_response.category} ({category_response.confidence})"
        )
        return category_response

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
        description: str,
        amount: float,
        date: str,
    ) -> str:
        """Build a prompt for the LLM to determine the transaction category with clear ID and name pairs.

        Args:
            description: The raw transaction description
            amount: Transaction amount
            date: Transaction date

        Returns:
            A formatted prompt string for the LLM.
        """
        # Include transaction details
        prompt = (
            f"Given this transaction information:\n"
            f"Description: {description}\n"
            f"Amount: ${amount:.2f}\n"
            f"Date: {date}\n"
        )

        # Add business context
        if self.business_context:
            prompt += f"\nBusiness Context:\n{self.business_context}\n"

        # Add available categories with their IDs
        prompt += "\nAvailable Categories (ID: Category Name):\n"
        # Sort by ID for consistent ordering
        sorted_categories = sorted(CATEGORY_MAPPING.items(), key=lambda x: x[1])
        for category_name, category_id in sorted_categories:
            prompt += f"{category_id}: {category_name}\n"

        # Clear instructions on response format
        prompt += (
            "\nPLEASE SELECT ONE CATEGORY from the list above.\n"
            "You MUST return the category NAME, not the ID number.\n\n"
            "Format your response as JSON with these fields:\n"
            "- category: The exact name of the chosen category (NOT the ID)\n"
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
        """Build a prompt for the LLM to determine tax classification.

        Args:
            transaction_description: Transaction description
            payee: The payee name
            category: Category from Pass 2
            amount: Transaction amount
            date: Transaction date

        Returns:
            A formatted prompt string for the LLM.
        """
        # Include transaction details and business context
        prompt = (
            f"Given this transaction information:\n"
            f"Description: {transaction_description}\n"
            f"Payee: {payee}\n"
            f"Category (from prior step): {category}\n"
            f"Amount: ${amount:.2f}\n"
            f"Date: {date}\n"
        )

        # Add business context
        if self.business_context:
            prompt += f"\nBusiness Context:\n{self.business_context}\n"

        # Add tax categories with clear headers and formatting
        prompt += "\n## TAX CATEGORIES\n"
        prompt += (
            "Each category has a numeric ID and belongs to a specific worksheet.\n"
        )
        prompt += "ID: Category Name (Worksheet)\n"
        prompt += "---------------------------------\n"

        # Sort by ID for consistent ordering
        sorted_business_categories = sorted(self.business_categories_by_id.items())

        for cat_id, (name, worksheet) in sorted_business_categories:
            prompt += f"{cat_id}: {name} (Worksheet: {worksheet})\n"

        # Special note for Personal expenses
        prompt += f"\nNOTE: If this is a personal expense, use category ID {self.personal_category_id}.\n\n"

        # Specify allowed worksheet values
        allowed_worksheets = sorted(list(self.ALLOWED_WORKSHEETS))
        prompt += f"## WORKSHEET VALUES\n"
        prompt += f"You MUST ONLY use one of these exact worksheet values:\n"
        prompt += f"{', '.join(allowed_worksheets)}\n\n"
        prompt += f"RULES:\n"
        prompt += f"- Personal expenses MUST use 'Personal' as the worksheet\n"
        prompt += f"- Business expenses must NEVER use 'Personal' as the worksheet\n"
        prompt += f"- DO NOT use 'T2125', 'T776', or any other worksheet name not in the list above\n\n"

        # Clear response format instructions
        prompt += f"## RESPONSE FORMAT\n"
        prompt += (
            "You must ONLY reply in this exact JSON format:\n"
            "{\n"
            '  "tax_category_id": [numeric ID from the list above],\n'
            '  "business_percentage": [0-100],\n'
            '  "worksheet": ["6A", "Vehicle", "HomeOffice", or "Personal"],\n'
            '  "confidence": ["high", "medium", or "low"],\n'
            '  "reasoning": "Your explanation here"\n'
            "}\n\n"
            "Remember: tax_category_id must be a NUMBER, not a string!"
        )
        return prompt

    def _get_tax_classification(
        self, transaction: TransactionInfo, force_process: bool = False
    ) -> TaxInfo:
        """Get tax classification for a BUSINESS transaction."""
        try:
            # CRITICAL CHECK: If transaction was categorized as personal in Pass 2,
            # return a Personal TaxInfo object immediately without consulting the AI
            if (
                transaction.category_info
                and transaction.category_info.expense_type == "personal"
            ):
                logger.info(
                    f"Transaction ID {transaction.transaction_id} was categorized as personal in Pass 2, enforcing Personal worksheet"
                )
                return TaxInfo(
                    tax_category_id=self.personal_category_id,
                    tax_category="Personal Expense",
                    business_percentage=0,
                    worksheet="Personal",
                    confidence="high",
                    reasoning="Enforcing personal classification from category assignment phase",
                )

            # This method now assumes the transaction is NOT personal.
            # Personal transactions should be handled earlier in process_transactions.

            # If force_process is True, skip matching and mapping, go directly to AI
            if force_process:
                logger.info(
                    f"🧠 FORCED AI tax classification for [{transaction.transaction_id}]"
                )
            else:
                # Only try matching if we're not forcing AI processing
                # First try to find a matching transaction based on description
                match_data = self._find_matching_transaction(transaction.description)
                if (
                    match_data
                    and match_data.get("tax_category_id") is not None
                    and match_data.get("is_personal") is False
                ):
                    logger.info(
                        f"✓ Using existing BUSINESS classification from description match"
                    )
                    # Verify the matched ID exists in our current business categories
                    if match_data["tax_category_id"] in self.business_categories_by_id:
                        cat_name, ws_name = self.business_categories_by_id[
                            match_data["tax_category_id"]
                        ]
                        return TaxInfo(
                            tax_category_id=match_data["tax_category_id"],
                            tax_category=cat_name,  # Get name from mapping
                            business_percentage=match_data.get(
                                "business_percentage", 100
                            ),
                            worksheet=match_data.get(
                                "worksheet", ws_name
                            ),  # Use matched or mapped worksheet
                            confidence=match_data.get(
                                "classification_confidence", "medium"
                            ),
                            reasoning="Using existing classification from matching transaction",
                        )
                    else:
                        logger.warning(
                            f"Matched transaction has tax_category_id {match_data['tax_category_id']} which is not a known business category. Proceeding with AI."
                        )

                # If no description match, try to map directly from Pass 2 category name to a BUSINESS tax category
                if transaction.category_info:
                    # Check if the Pass 2 category maps to a known business category ID
                    # Assumes transaction.category_info.category holds the general category name from Pass 2
                    pass2_cat_name = transaction.category_info.category
                    for (
                        name,
                        worksheet,
                    ), cat_id in self.business_category_id_by_name_ws.items():
                        if name.lower() == pass2_cat_name.lower():
                            logger.info(
                                f"✓ Found direct business tax category map: {name} (ID: {cat_id}) from Pass 2 category '{pass2_cat_name}'"
                            )
                            return TaxInfo(
                                tax_category_id=cat_id,
                                tax_category=name,
                                business_percentage=transaction.category_info.business_percentage,
                                worksheet=worksheet,
                                confidence=transaction.category_info.confidence,
                                reasoning=f"Mapped directly from Pass 2 category: {pass2_cat_name}",
                            )
                            break  # Found first match

            # --- AI Classification --- #
            # If we get here, either force_process is True or no matches were found
            logger.info(
                f"🧠 Using AI for BUSINESS tax classification... [{transaction.transaction_id}]"
                + (" (Forced)" if force_process else "")
            )
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
                        "content": "You are a transaction classification assistant providing JSON responses for business expenses. ONLY use these EXACT worksheet values: '6A', 'Vehicle', 'HomeOffice', or 'Personal'. Personal expenses MUST use 'Personal' as the worksheet. Business expenses must NEVER use 'Personal' as the worksheet. DO NOT use T2125, T776, or any other tax form names - these will cause database validation errors.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            result_str = response.choices[0].message.content
            try:
                # Parse the JSON but validate/modify the worksheet before creating the ClassificationResponse
                result = json.loads(result_str)

                # Validate worksheet value before creating the model
                allowed_worksheets = self.ALLOWED_WORKSHEETS

                # First determine if this is a personal expense
                is_personal = False
                if result.get("tax_category_id") == self.personal_category_id:
                    is_personal = True
                    result["worksheet"] = (
                        "Personal"  # Always use Personal worksheet for personal expenses
                    )

                # Handle case where worksheet is a list instead of a string
                worksheet_value = result.get("worksheet", "")
                if isinstance(worksheet_value, list):
                    logger.warning(
                        f"Worksheet value is a list: {worksheet_value}, extracting first value or defaulting to '6A'"
                    )
                    # Take the first value if the list is not empty, otherwise default to '6A'
                    if worksheet_value and isinstance(worksheet_value[0], str):
                        result["worksheet"] = worksheet_value[0]
                    else:
                        result["worksheet"] = "6A"

                # Handle case where confidence is a list instead of a string
                confidence_value = result.get("confidence", "")
                if isinstance(confidence_value, list):
                    logger.warning(
                        f"Confidence value is a list: {confidence_value}, extracting first value or defaulting to 'medium'"
                    )
                    # Take the first value if the list is not empty, otherwise default to 'medium'
                    if confidence_value and isinstance(confidence_value[0], str):
                        result["confidence"] = confidence_value[0]
                    else:
                        result["confidence"] = "medium"

                # Only apply worksheet mapping for business expenses
                elif (
                    not is_personal
                    and result.get("worksheet") not in allowed_worksheets
                ):
                    # Map common variations to allowed values
                    worksheet_mapping = {
                        "T2125": "6A",
                        "T1": "6A",
                        "T2": "6A",
                        "Schedule": "6A",
                        "Business": "6A",
                        "Auto": "Vehicle",
                        "Car": "Vehicle",
                        "Home": "HomeOffice",
                        "Office": "HomeOffice",
                        "Rental": "6A",
                        "RentalProperty": "6A",
                        "T776": "6A",
                        "Employment": "6A",
                        "Work": "6A",
                        "T777": "6A",
                    }

                    mapped = False
                    raw_worksheet = result.get("worksheet", "")
                    for key, value in worksheet_mapping.items():
                        if key.lower() in raw_worksheet.lower():
                            logger.warning(
                                f"Mapping worksheet '{raw_worksheet}' to '{value}'."
                            )
                            result["worksheet"] = value
                            mapped = True
                            break

                    # If mapping fails, leave as is if it's a valid tax form
                    if not mapped:
                        if (
                            raw_worksheet.startswith("T")
                            and raw_worksheet[1:].isdigit()
                        ):
                            # It appears to be a tax form (T + numbers), keep it
                            logger.info(
                                f"Keeping tax form worksheet name: {raw_worksheet}"
                            )
                            result["worksheet"] = raw_worksheet
                        else:
                            # Use 6A only as a last resort
                            logger.warning(
                                f"Unrecognized worksheet '{raw_worksheet}'. Using '6A'."
                            )
                            result["worksheet"] = "6A"

                # Final validation - Make sure we ALWAYS have a valid worksheet value before creating the model
                worksheet_value = result.get("worksheet")
                if isinstance(worksheet_value, list):
                    logger.warning(
                        f"Final worksheet value is still a list: {worksheet_value}, forcing to '6A'"
                    )
                    result["worksheet"] = "6A"
                elif worksheet_value not in allowed_worksheets:
                    logger.warning(
                        f"Invalid worksheet '{worksheet_value}' found before model creation. Forcing to '6A'."
                    )
                    result["worksheet"] = "6A"  # Force to 6A as a fallback

                # Final validation for confidence value
                confidence_value = result.get("confidence")
                if isinstance(confidence_value, list):
                    logger.warning(
                        f"Final confidence value is still a list: {confidence_value}, forcing to 'medium'"
                    )
                    result["confidence"] = "medium"
                elif confidence_value not in ["high", "medium", "low"]:
                    logger.warning(
                        f"Invalid confidence value '{confidence_value}' found before model creation. Forcing to 'medium'."
                    )
                    result["confidence"] = "medium"  # Force to medium as a fallback

                # Now create the ClassificationResponse with validated data
                classification = ClassificationResponse(**result)
            except (json.JSONDecodeError, PydanticValidationError) as json_error:
                logger.error(
                    f"❌ Error parsing AI JSON response for tax classification: {json_error}"
                )
                logger.error(f"Raw AI Response: {result_str}")
                # Fallback or re-prompt logic could go here
                return TaxInfo(
                    tax_category_id=0,  # Or a default error ID if you create one
                    tax_category="Error Parsing AI Response",
                    business_percentage=0,
                    worksheet="Unknown",
                    confidence="low",
                    reasoning=f"Error parsing AI JSON: {json_error}",
                )

            return TaxInfo(
                tax_category_id=classification.tax_category_id,
                tax_category=classification.tax_category,
                business_percentage=classification.business_percentage,
                worksheet=classification.worksheet,
                confidence=classification.confidence,
                reasoning=classification.reasoning,
            )

        except Exception as e:
            logger.error(
                f"❌ Error getting tax classification for transaction {transaction.transaction_id}: {str(e)}"
            )
            logger.error(traceback.format_exc())
            return TaxInfo(
                tax_category_id=0,
                tax_category="Classification Error",
                business_percentage=0,
                worksheet="Unknown",
                confidence="low",
                reasoning=f"Error during classification: {str(e)}",
            )

    def _validate_ai_response(
        self, response: ClassificationResponse
    ) -> ClassificationResponse:
        """
        This method is now deprecated. Validation happens inside _get_tax_classification.
        Kept for backward compatibility.
        """
        return response

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

    def _categorize_transaction_pass_1(
        self, transaction: dict, force_process: bool = False
    ) -> TransactionInfo:
        """First pass of transaction categorization - basic categorization.

        Assigns transaction to a high-level category (like Personal, Business Expense, etc.)

        Args:
            transaction: A dictionary containing transaction data
            force_process: Whether to force AI processing, bypassing cache

        Returns:
            TransactionInfo with payee and category assigned
        """
        try:
            # Extract transaction details
            description = self._clean_text(transaction.get("description", ""))
            amount = float(transaction.get("amount", 0))
            date = transaction.get("date", "")

            # Get a unique identifier for this transaction
            transaction_id = transaction.get("id", str(uuid.uuid4()))

            # Get the cache key
            cache_key = self._get_cache_key(
                description, amount, date, pass_type="Pass1"
            )

            # Initialize transaction info
            transaction_info = TransactionInfo(
                id=transaction_id, description=description, date=date, amount=amount
            )

            # Get payee (may use AI)
            payee = self._get_payee(description, force_process)
            transaction_info.payee_info = payee

            # Attempt to get category
            category, confidence, notes, expense_type, business_percentage = (
                self._get_category(
                    description=description,
                    amount=amount,
                    date=date,
                    payee=payee,
                    force_process=force_process,
                )
            )

            # Update transaction info with category data
            transaction_info.category_info = category
            transaction_info.confidence = confidence
            transaction_info.notes = notes
            transaction_info.expense_type = expense_type
            transaction_info.business_percentage = business_percentage

            # Return the transaction info
            return transaction_info

        except Exception as e:
            # Log the exception
            self.logger.error(f"Error in Pass 1 categorization: {str(e)}")
            self.logger.error(traceback.format_exc())

            # Return default transaction info
            return TransactionInfo(
                id=transaction.get("id", str(uuid.uuid4())),
                description=transaction.get("description", ""),
                date=transaction.get("date", ""),
                amount=float(transaction.get("amount", 0)),
                category="Error",
                confidence="low",
                notes=f"Error in categorization: {str(e)}",
                expense_type="Unknown",
                business_percentage=0,
            )

    # After the _process_worksheet_assignment method and before the next method

    def _get_existing_category(self, transaction_id: str) -> Optional[Dict]:
        """Get existing category information for a transaction.

        Args:
            transaction_id: ID of the transaction

        Returns:
            Dictionary with category information including expense_type, or None if not found
        """
        try:
            logger.info(
                f"Getting existing category info for transaction ID: {transaction_id}"
            )

            # Query to get category information from transaction_classifications table
            query = """
                SELECT category, category_confidence, category_reasoning, expense_type, business_percentage
                FROM transaction_classifications
                WHERE transaction_id = ?
            """
            result = self.db.execute_query(query, (transaction_id,))

            if not result or not result[0]:
                logger.info(
                    f"No category information found for transaction ID: {transaction_id}"
                )
                return None

            row = result[0]

            # Log the retrieved data for debugging
            logger.info(
                f"Found category data for transaction ID {transaction_id}: {row}"
            )

            # Return category information as dictionary
            return {
                "base_category": row[0],  # category
                "confidence": row[1],  # category_confidence
                "reasoning": row[2],  # category_reasoning
                "expense_type": row[3],  # expense_type
                "business_percentage": row[4],  # business_percentage
            }

        except Exception as e:
            logger.error(
                f"Error getting category info for transaction {transaction_id}: {str(e)}"
            )
            logger.error(traceback.format_exc())
            return None

    def _determine_worksheet(
        self, transaction: pd.Series, base_category: str
    ) -> WorksheetAssignment:
        """Determine the worksheet for a transaction based on its category.

        Args:
            transaction: Transaction row from DataFrame
            base_category: Base category from Pass 2

        Returns:
            WorksheetAssignment with worksheet, tax_category, and tax_subcategory
        """
        logger.info(
            f"Determining worksheet for transaction ID: {transaction['transaction_id']}"
        )

        # First check if this is a personal expense based on existing classification
        # Get existing category info to check expense_type
        category_info = self._get_existing_category(transaction["transaction_id"])

        if category_info and category_info.get("expense_type") == "personal":
            logger.info(
                f"Transaction ID {transaction['transaction_id']} is a personal expense, assigning to Personal worksheet"
            )
            return WorksheetAssignment(
                worksheet="Personal",
                tax_category="Personal Expense",
                tax_subcategory="",
            )

        # For business expenses, use the normal mapping
        try:
            # Get the appropriate worksheet based on category
            worksheet = get_worksheet_for_category(base_category)

            # Ensure worksheet is in allowed values
            if worksheet not in self.ALLOWED_WORKSHEETS:
                logger.warning(
                    f"Invalid worksheet '{worksheet}' for category '{base_category}', defaulting to '6A'"
                )
                worksheet = "6A"

            logger.info(
                f"Assigned worksheet '{worksheet}' to transaction ID {transaction['transaction_id']}"
            )

            return WorksheetAssignment(
                worksheet=worksheet,
                tax_category=base_category,
                tax_subcategory="",  # This could be refined in future versions
            )

        except Exception as e:
            logger.error(
                f"Error determining worksheet for transaction {transaction['transaction_id']}: {str(e)}"
            )
            logger.error(traceback.format_exc())

            # Default to 6A in case of error
            return WorksheetAssignment(
                worksheet="6A", tax_category=base_category, tax_subcategory=""
            )
