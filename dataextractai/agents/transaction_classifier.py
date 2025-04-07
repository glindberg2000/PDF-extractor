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
from typing import Dict, List, Optional
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
        logging.DEBUG: Fore.CYAN + "%(message)s" + Style.RESET_ALL,
        logging.INFO: "%(message)s",
        logging.WARNING: Fore.YELLOW + "%(message)s" + Style.RESET_ALL,
        logging.ERROR: Fore.RED + "%(message)s" + Style.RESET_ALL,
        logging.CRITICAL: Fore.RED + Style.BRIGHT + "%(message)s" + Style.RESET_ALL,
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


class TransactionClassifier:
    def __init__(self, client_name: str, db: ClientDB, model_type: str = "fast"):
        """Initialize the transaction classifier.

        Args:
            client_name: Name of the client
            db: Database instance
            model_type: Type of model to use ("fast" or "precise"), defaults to "fast"
        """
        self.client_name = client_name
        self.db = db
        self.client = OpenAI()
        self._persistent_conn = None  # For batch processing
        self.profile_manager = ClientProfileManager(client_name)
        self.business_profile = self.profile_manager._load_profile()
        self.model_type = model_type

        # Load standard categories
        self.standard_categories = list(
            TAX_WORKSHEET_CATEGORIES["6A"]["main_expenses"].keys()
        )

        # Load client's custom categories
        self.client_categories = self._load_client_categories()

        # Combine all available categories
        self.all_categories = self.standard_categories + self.client_categories

        # Get business context for AI prompts
        self.business_context = self._get_business_context()

        logger.info(
            f"{Fore.GREEN}▶ Initialized Transaction Classifier for client: {self.client_name}{Style.RESET_ALL}"
        )
        logger.info(f"  • Model type: {self.model_type}")
        logger.info(f"  • Standard categories: {len(self.standard_categories)}")
        logger.info(f"  • Custom categories: {len(self.client_categories)}")

    def _start_batch_processing(self):
        """Start batch processing by establishing a persistent connection."""
        if not self._persistent_conn:
            self._persistent_conn = sqlite3.connect(
                self.db.db_path, isolation_level=None
            )
            logger.debug("Established persistent connection for batch processing")

    def _end_batch_processing(self):
        """End batch processing by closing the persistent connection."""
        if self._persistent_conn:
            self._persistent_conn.close()
            self._persistent_conn = None
            logger.debug("Closed persistent connection for batch processing")

    def _load_client_categories(self) -> List[str]:
        """Load client-specific categories from the database."""
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT category_name 
                FROM client_expense_categories 
                WHERE client_id = ? AND tax_year = strftime('%Y', 'now')
                """,
                (self.db.get_client_id(self.client_name),),
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
        self, description: str, payee: str = None, category: str = None
    ) -> str:
        """Generate a consistent cache key.

        Args:
            description: Raw transaction description
            payee: Optional standardized payee name
            category: Optional category name

        Returns:
            Consistent cache key string
        """
        # Always start with cleaned description
        clean_desc = self._clean_description(description)

        # Detailed logging for key generation
        logger.debug(f"Generating cache key - Input values:")
        logger.debug(f"  • Raw description: {repr(description)}")
        logger.debug(f"  • Cleaned description: {repr(clean_desc)}")
        logger.debug(f"  • Raw payee: {repr(payee)}")
        logger.debug(f"  • Raw category: {repr(category)}")

        key_parts = [clean_desc]

        # Only add payee if it's standardized and different from description
        if payee:
            clean_payee = self._clean_description(payee)
            logger.debug(f"  • Cleaned payee: {repr(clean_payee)}")
            if clean_payee != clean_desc:
                key_parts.append(clean_payee)

        # Add category if provided
        if category:
            clean_category = category.lower()
            logger.debug(f"  • Cleaned category: {repr(clean_category)}")
            key_parts.append(clean_category)

        cache_key = "|".join(key_parts)
        logger.debug(f"  • Final cache key: {repr(cache_key)}")

        return cache_key

    def _get_cached_result(self, cache_key: str, pass_type: str) -> Optional[Dict]:
        """Get a cached result from the database."""
        logger.debug(f"Checking cache for key: {cache_key} (pass: {pass_type})")

        # Use persistent connection if available, otherwise create a new one
        conn = self._persistent_conn or sqlite3.connect(
            self.db.db_path, isolation_level=None
        )
        try:
            cursor = conn.execute(
                """
                SELECT result
                FROM transaction_cache
                WHERE client_id = ? AND cache_key = ? AND pass_type = ?
                """,
                (self.db.get_client_id(self.client_name), cache_key, pass_type),
            )
            result = cursor.fetchone()
            if result:
                logger.info(
                    f"{Fore.CYAN}[CACHE HIT] Found cached {pass_type} result for: {cache_key}{Style.RESET_ALL}"
                )
                cached = json.loads(result[0])

                # Log cache contents for debugging
                logger.debug(f"Cache hit contents: {json.dumps(cached, indent=2)}")

                # Handle legacy cache format for category responses
                if pass_type == "category":
                    return {
                        "category": cached.get("category", ""),
                        "expense_type": cached.get("expense_type", "personal"),
                        "business_percentage": int(
                            cached.get("business_percentage", 0)
                        ),
                        "notes": cached.get("reasoning", ""),
                        "confidence": cached.get("confidence", "medium"),
                        "detailed_context": cached.get("business_context", ""),
                    }
                return cached
            else:
                logger.debug(f"No cache hit for key: {cache_key}")
                return None
        finally:
            # Only close the connection if it's not the persistent one
            if not self._persistent_conn and conn:
                conn.close()

    def _cache_result(self, cache_key: str, pass_type: str, result: Dict) -> None:
        """Save a result to the database cache."""
        client_id = self.db.get_client_id(self.client_name)

        # Log cache write attempt
        logger.debug(f"Attempting to cache result:")
        logger.debug(f"  • Cache key: {cache_key}")
        logger.debug(f"  • Pass type: {pass_type}")
        logger.debug(f"  • Result: {json.dumps(result, indent=2)}")

        # Use persistent connection if available, otherwise create a new one
        conn = self._persistent_conn or sqlite3.connect(
            self.db.db_path, isolation_level=None
        )
        try:
            conn.execute(
                """
                INSERT INTO transaction_cache (client_id, cache_key, pass_type, result)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (client_id, cache_key, pass_type) 
                DO UPDATE SET result = ?, updated_at = CURRENT_TIMESTAMP
                """,
                (
                    client_id,
                    cache_key,
                    pass_type,
                    json.dumps(result),
                    json.dumps(result),
                ),
            )
            logger.debug(f"Cache write completed successfully")
        finally:
            # Only close the connection if it's not the persistent one
            if not self._persistent_conn and conn:
                conn.close()

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
            skipped_count = {1: 0, 2: 0, 3: 0}
            processed_count = {1: 0, 2: 0, 3: 0}
            error_count = {1: 0, 2: 0, 3: 0}
            cache_hit_count = {1: 0, 2: 0, 3: 0}

            # Process transactions row by row
            for idx in range(start_row, end_row):
                transaction = transactions.iloc[idx]
                row_number = idx + 1
                row_info = f"[Row {row_number}]"

                try:
                    # Check if transaction is already fully processed
                    if not force_process:
                        status = self.db.get_transaction_status(
                            self.client_name, transaction["transaction_id"]
                        )
                        if status:
                            skip_this_row = False
                            for pass_num in range(resume_from_pass, 4):
                                if status.get(f"pass_{pass_num}_status") == "completed":
                                    if pass_num == resume_from_pass:
                                        logger.info(
                                            f"{Fore.CYAN}[Row {row_number}] ✓ Already processed pass {pass_num}, skipping...{Style.RESET_ALL}"
                                        )
                                        skip_this_row = True
                                        skipped_count[pass_num] += 1
                                        break
                            if skip_this_row:
                                continue

                    # Log separator for visual clarity
                    logger.info(f"\n{Fore.CYAN}{'─'*80}{Style.RESET_ALL}")
                    logger.info(
                        f"{Fore.CYAN}[Row {row_number}] Transaction: {transaction['description']}{Style.RESET_ALL}"
                    )

                    # Pass 1: Payee identification
                    if resume_from_pass == 1:
                        logger.info(
                            f"{Fore.GREEN}▶ PASS 1: Payee Identification{Style.RESET_ALL}"
                        )

                        # Get payee info
                        payee_info = self._get_payee(
                            transaction["description"],
                            row_info=row_info,
                            force_process=force_process,
                        )

                        # Update transaction with payee info
                        update_data = {
                            "client_id": self.db.get_client_id(self.client_name),
                            "payee": payee_info.payee,
                            "payee_confidence": payee_info.confidence,
                            "payee_reasoning": payee_info.reasoning,
                            "business_description": payee_info.business_description,
                            "general_category": payee_info.general_category,
                        }

                        self.db.update_transaction_classification(
                            transaction["transaction_id"], update_data
                        )

                        # Cache the result with all fields
                        cache_key = self._get_cache_key(transaction["description"])
                        cached_payee = self._get_cached_result(cache_key, "payee")
                        if not cached_payee:
                            self._cache_result(
                                cache_key,
                                "payee",
                                {
                                    "payee": payee_info.payee,
                                    "confidence": payee_info.confidence,
                                    "reasoning": payee_info.reasoning,
                                    "business_description": payee_info.business_description,
                                    "general_category": payee_info.general_category,
                                },
                            )

                        # Update status
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "client_id": self.db.get_client_id(self.client_name),
                                "pass_1_status": "completed",
                                "pass_1_error": None,
                                "pass_1_processed_at": datetime.now(),
                            },
                        )

                        logger.info(
                            f"{Fore.GREEN}✓ Pass 1 complete: {payee_info.payee} ({payee_info.confidence}){Style.RESET_ALL}"
                        )
                        if payee_info.business_description:
                            logger.info(
                                f"  • Business Description: {payee_info.business_description}"
                            )
                            logger.info(
                                f"  • General Category: {payee_info.general_category}"
                            )
                        processed_count[1] += 1

                        # If we're only doing pass 1, continue to next transaction
                        if resume_from_pass == 1:
                            continue

                    # Pass 2: Category assignment
                    if resume_from_pass <= 2:
                        logger.info(
                            f"{Fore.GREEN}▶ PASS 2: Category Assignment{Style.RESET_ALL}"
                        )

                        # Get existing payee info
                        existing = self.db.get_transaction_classification(
                            transaction["transaction_id"]
                        )
                        if not existing or not existing.get("payee"):
                            logger.warning(
                                f"{row_info} ⚠ No payee found from pass 1, skipping pass 2"
                            )
                            continue

                        # Check cache for category
                        cache_key = self._get_cache_key(
                            transaction["description"], existing["payee"]
                        )
                        cached_category = self._get_cached_result(cache_key, "category")

                        if cached_category and not force_process:
                            logger.info(
                                f"{row_info} ✓ Using cached category: {cached_category['category']} (confidence: {cached_category['confidence']})"
                            )
                            category_info = CategoryResponse(**cached_category)
                            cache_hit_count[2] += 1
                        else:
                            # Get category info from LLM
                            logger.info(
                                f"{row_info} 🤖 Getting category for: {existing['payee']}"
                            )
                            category_info = self._get_category(
                                transaction["description"],
                                transaction["amount"],
                                transaction["transaction_date"].strftime("%Y-%m-%d"),
                                payee=existing["payee"],
                                business_description=existing.get(
                                    "business_description"
                                ),
                                general_category=existing.get("general_category"),
                                force_process=force_process,
                                row_info=row_info,
                            )
                            logger.info(
                                f"{row_info} ✓ Category assigned: {category_info.category} (confidence: {category_info.confidence})"
                            )

                            # Extract fields from category_info
                            expense_type = "personal"  # Default to personal
                            business_percentage = 0  # Default to 0%
                            business_context = ""

                            if category_info.notes:
                                # Extract expense type
                                expense_type_match = re.search(
                                    r"Expense type:\s*(business|personal|mixed)",
                                    category_info.notes.lower(),
                                )
                                if expense_type_match:
                                    expense_type = expense_type_match.group(1)

                                # Extract business percentage
                                percentage_match = re.search(
                                    r"Business percentage:\s*(\d+)%",
                                    category_info.notes,
                                )
                                if percentage_match:
                                    business_percentage = int(percentage_match.group(1))
                                    # Ensure expense_type is consistent with business_percentage
                                    if business_percentage == 100:
                                        expense_type = "business"
                                    elif business_percentage == 0:
                                        expense_type = "personal"
                                    elif business_percentage > 0:
                                        expense_type = "mixed"

                                # Extract business context
                                context_match = re.search(
                                    r"Business context:\s*([^\n]+)", category_info.notes
                                )
                                if context_match:
                                    business_context = context_match.group(1).strip()

                            # Update transaction with category info
                            update_data = {
                                "client_id": self.db.get_client_id(self.client_name),
                                "category": str(category_info.category),
                                "category_confidence": str(category_info.confidence),
                                "category_reasoning": str(category_info.notes),
                                "expense_type": str(category_info.expense_type),
                                "business_percentage": int(
                                    category_info.business_percentage
                                ),
                                "business_context": str(
                                    category_info.detailed_context or ""
                                ),
                                "classification": str(
                                    "Business"
                                    if category_info.expense_type == "business"
                                    else (
                                        "Personal"
                                        if category_info.expense_type == "personal"
                                        else "Unclassified"  # Map 'mixed' to 'Unclassified'
                                    )
                                ),
                                "classification_confidence": str(
                                    category_info.confidence
                                ),
                            }

                            # Log what we're updating
                            logger.info(
                                f"{row_info} Updating transaction {transaction['transaction_id']} with:"
                            )
                            for key, value in update_data.items():
                                logger.info(f"  • {key}: {value}")

                            # Update the database
                            self.db.update_transaction_classification(
                                transaction["transaction_id"], update_data
                            )

                            # Cache the result
                            self._cache_result(
                                cache_key,
                                "category",
                                {
                                    "category": str(category_info.category),
                                    "expense_type": str(category_info.expense_type),
                                    "business_percentage": int(
                                        category_info.business_percentage
                                    ),
                                    "notes": str(category_info.notes),
                                    "confidence": str(category_info.confidence),
                                    "detailed_context": str(
                                        category_info.detailed_context or ""
                                    ),
                                },
                            )

                        # Update status
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "client_id": self.db.get_client_id(self.client_name),
                                "pass_2_status": "completed",
                                "pass_2_error": None,
                                "pass_2_processed_at": datetime.now(),
                            },
                        )

                        logger.info(
                            f"{Fore.GREEN}✓ Pass 2 complete: {category_info.category} ({category_info.expense_type}){Style.RESET_ALL}"
                        )
                        processed_count[2] += 1

                        # If we're only doing up to pass 2, continue to next transaction
                        if resume_from_pass == 2:
                            continue

                    # Pass 3: Tax Classification
                    if resume_from_pass <= 3:
                        logger.info(
                            f"{Fore.GREEN}▶ PASS 3: Tax Classification{Style.RESET_ALL}"
                        )

                        # Get existing category info
                        existing = self.db.get_transaction_classification(
                            transaction["transaction_id"]
                        )
                        if not existing or not existing.get("base_category"):
                            logger.warning(
                                f"{row_info} ⚠ No category found from pass 2, skipping pass 3"
                            )
                            continue

                        # Skip personal expenses from detailed tax classification
                        if existing.get("expense_type") == "personal":
                            logger.info(
                                f"{row_info} ℹ Personal expense, setting minimal tax classification"
                            )
                            classification_info = ClassificationResponse(
                                tax_category="Not Applicable",
                                tax_subcategory="Personal Expense",
                                worksheet="6A",
                                confidence="high",
                                reasoning="This is a personal expense and not applicable for tax deductions.",
                            )
                            cache_hit_count[3] += 1
                        else:
                            # Get classification info from LLM
                            logger.info(
                                f"{row_info} 🤖 Getting tax classification for: {existing['base_category']}"
                            )
                            classification_info = self._get_classification(
                                transaction["description"],
                                existing["payee"],
                                existing["base_category"],
                                existing.get("expense_type", "business"),
                                existing.get("business_percentage", 100),
                                existing.get("business_description"),
                                existing.get("general_category"),
                                existing.get("business_context"),
                                force_process=force_process,
                                row_info=row_info,
                            )
                            logger.info(
                                f"{row_info} ✓ Tax classification: {classification_info.tax_category} (confidence: {classification_info.confidence})"
                            )

                        # Update transaction with classification info
                        update_data = {
                            "client_id": self.db.get_client_id(self.client_name),
                            "tax_category": classification_info.tax_category,
                            "tax_subcategory": classification_info.tax_subcategory,
                            "worksheet": classification_info.worksheet,
                            "classification_confidence": classification_info.confidence,
                            "classification_reasoning": classification_info.reasoning,
                        }

                        self.db.update_transaction_classification(
                            transaction["transaction_id"], update_data
                        )

                        # Cache the result
                        if (
                            not existing.get("expense_type") == "personal"
                            and not classification_info
                        ):
                            self._cache_result(
                                cache_key,
                                "classification",
                                {
                                    "tax_category": classification_info.tax_category,
                                    "tax_subcategory": classification_info.tax_subcategory,
                                    "worksheet": classification_info.worksheet,
                                    "confidence": classification_info.confidence,
                                    "reasoning": classification_info.reasoning,
                                },
                            )

                        # Update status
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "client_id": self.db.get_client_id(self.client_name),
                                "pass_3_status": "completed",
                                "pass_3_error": None,
                                "pass_3_processed_at": datetime.now(),
                            },
                        )

                        logger.info(
                            f"{Fore.GREEN}✓ Pass 3 complete: {classification_info.tax_category} (worksheet: {classification_info.worksheet}){Style.RESET_ALL}"
                        )
                        processed_count[3] += 1

                except Exception as e:
                    error_message = (
                        f"Error processing transaction {row_number}: {str(e)}"
                    )
                    logger.error(f"{Fore.RED}❌ {error_message}{Style.RESET_ALL}")
                    error_count[resume_from_pass] += 1

                    # Update error status for the current pass
                    error_status = {
                        "client_id": self.db.get_client_id(self.client_name),
                        f"pass_{resume_from_pass}_status": "error",
                        f"pass_{resume_from_pass}_error": str(e),
                        f"pass_{resume_from_pass}_processed_at": datetime.now(),
                    }
                    self.db.update_transaction_status(
                        transaction["transaction_id"], error_status
                    )

            # Print summary statistics
            logger.info(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")
            logger.info(
                f"{Fore.GREEN}▶ Transaction Processing Summary{Style.RESET_ALL}"
            )
            for pass_num in range(resume_from_pass, 4):
                if pass_num <= 3:
                    logger.info(f"  • Pass {pass_num} ({pass_desc.get(pass_num)})")
                    logger.info(f"    - Processed: {processed_count.get(pass_num, 0)}")
                    logger.info(f"    - Skipped: {skipped_count.get(pass_num, 0)}")
                    logger.info(f"    - Cache hits: {cache_hit_count.get(pass_num, 0)}")
                    logger.info(f"    - Errors: {error_count.get(pass_num, 0)}")

            logger.info(f"{Fore.GREEN}{'='*80}{Style.RESET_ALL}\n")
            logger.info(
                f"{Fore.GREEN}Transaction processing complete!{Style.RESET_ALL}"
            )

        finally:
            # Always ensure we close the persistent connection
            self._end_batch_processing()

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
                (self.db.get_client_id(self.client_name), pass_number),
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
                self.db.save_transaction_classification(
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

    def _get_payee(
        self,
        description: str,
        profile: Optional[Dict] = None,
        industry_keywords: Optional[List[str]] = None,
        force_process: bool = False,
        row_info: str = "",
    ) -> PayeeResponse:
        """Get payee information for a transaction."""
        # Clean description for consistent matching
        clean_desc = self._clean_description(description)

        # Generate initial cache key from description only
        cache_key = self._get_cache_key(description)
        logger.info(f"{row_info} 🔍 Checking payee cache with key: {cache_key}")

        # Check cache first unless forced
        if not force_process:
            cached = self._get_cached_result(cache_key, "payee")
            if cached:
                # Validate cached result has required fields
                required_fields = {
                    "payee",
                    "business_description",
                    "general_category",
                    "confidence",
                }
                missing_fields = required_fields - set(cached.keys())

                # Use cache if complete and high/medium confidence
                if not missing_fields and cached.get("confidence") in [
                    "high",
                    "medium",
                ]:
                    logger.info(
                        f"{row_info} ✓ Using cached payee: {cached['payee']} (confidence: {cached['confidence']})"
                    )
                    return PayeeResponse(**cached)

                # Log why cache wasn't used
                if missing_fields:
                    logger.info(
                        f"{row_info} ⚠ Cache hit but missing fields: {', '.join(missing_fields)}. Will update..."
                    )
                else:
                    logger.info(
                        f"{row_info} ⚠ Low confidence cache hit ({cached.get('confidence')}), will try to improve..."
                    )
            else:
                logger.info(f"{row_info} ⚠ No payee cache hit, will compute")

        # Get client profile for industry keywords if not provided
        if not profile:
            profile = self.profile_manager._load_profile()
        if not industry_keywords and profile:
            industry_keywords = profile.get("industry_keywords", {})

        # Initialize result with default values
        result = {
            "payee": clean_desc,
            "business_description": "Could not determine business details",
            "general_category": "Unknown",
            "confidence": "low",
            "reasoning": "No vendor information found",
        }

        try:
            # Build prompt for initial analysis
            prompt = """Analyze this transaction description and identify if this is a well-known business or needs research:

Transaction: {description}

Business Context:
{business_context}

Industry Keywords:
{industry_keywords}

Rules:
1. For well-known businesses (e.g., Walmart, Target, McDonald's, etc.), provide details directly
2. For online merchants (e.g., Amazon, PayPal), standardize the name
3. For unclear or local businesses, indicate that research is needed
4. Remove transaction prefixes/suffixes and focus on the actual business name
5. Don't make assumptions based on business names alone
6. Consider transaction context and likely business type
7. Consider industry-specific keywords when analyzing business names

Respond with a JSON object containing:
{{
    "needs_research": true/false,
    "search_terms": "terms to search if research needed",
    "payee": "Business name if well-known, otherwise null",
    "business_description": "Description if well-known, otherwise null",
    "general_category": "Category if well-known, otherwise null",
    "confidence": "high, medium, or low",
    "reasoning": "Explanation of the identification"
}}""".format(
                description=description,
                business_context=profile.get("business_description", ""),
                industry_keywords=(
                    json.dumps(industry_keywords, indent=2)
                    if industry_keywords
                    else "None"
                ),
            )

            # Get completion from OpenAI
            response = self.client.chat.completions.create(
                model=self._get_model(),
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a payee identification assistant that provides JSON responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            # Parse response
            initial_analysis = json.loads(response.choices[0].message.content)

            # If it's a well-known business, use that directly
            if not initial_analysis.get("needs_research", True):
                logger.info(
                    f"{row_info} ✓ Identified as well-known business: {initial_analysis['payee']}"
                )
                result = {
                    "payee": initial_analysis["payee"],
                    "business_description": initial_analysis["business_description"],
                    "general_category": initial_analysis["general_category"],
                    "confidence": initial_analysis["confidence"],
                    "reasoning": initial_analysis["reasoning"],
                }
            else:
                # If research is needed, use the suggested search terms
                search_terms = initial_analysis.get("search_terms", clean_desc)
                logger.info(f"{row_info} 🔍 Looking up vendor info for: {search_terms}")

                try:
                    # Try first search with industry context
                    vendor_results = lookup_vendor_info(
                        search_terms,
                        max_results=15,
                        industry_keywords=industry_keywords,
                        search_query=(
                            f"{search_terms} {profile.get('business_type', '')}"
                            if profile
                            else None
                        ),
                    )

                    if vendor_results:
                        # Analyze all search results together
                        result = self._analyze_search_results(
                            search_terms, vendor_results, profile
                        )

                        if result and result.get("confidence") == "high":
                            logger.info(
                                f"{row_info} ✓ Found and verified vendor with industry context: {result['payee']}"
                            )
                            logger.info(
                                f"{row_info} 📋 Description: {result['business_description'][:200]}..."
                            )
                        else:
                            # If no high confidence match, try without industry context
                            logger.info(
                                f"{row_info} 🔍 Trying search without industry context..."
                            )
                            vendor_results_no_context = lookup_vendor_info(
                                search_terms, max_results=15
                            )

                            if vendor_results_no_context:
                                result = self._analyze_search_results(
                                    search_terms, vendor_results_no_context, profile
                                )
                                if result:
                                    logger.info(
                                        f"{row_info} ✓ Found vendor without industry context: {result['payee']}"
                                    )
                                    logger.info(
                                        f"{row_info} 📋 Description: {result['business_description'][:200]}..."
                                    )

                    if not result:
                        logger.info(f"{row_info} ⚠ No good search matches found")
                        # Fall back to initial analysis or cleaned description
                        result = {
                            "payee": clean_desc,
                            "business_description": "Could not determine business details",
                            "general_category": "Unknown",
                            "confidence": "low",
                            "reasoning": "No good vendor matches found",
                        }

                except Exception as e:
                    logger.warning(f"{row_info} ⚠ Vendor lookup failed: {str(e)}")
                    logger.warning(f"{row_info} ⚠ Traceback: {traceback.format_exc()}")
                    result = {
                        "payee": clean_desc,
                        "business_description": "Could not determine business details",
                        "general_category": "Unknown",
                        "confidence": "low",
                        "reasoning": f"Vendor lookup failed: {str(e)}",
                    }

            # Only cache if we have a new result with high/medium confidence
            if result and result.get("confidence") in ["high", "medium"]:
                # When caching results, use standardized key if we have a payee
                final_key = self._get_cache_key(description, result["payee"])
                if final_key != cache_key:
                    logger.info(
                        f"{row_info} 📝 Updating cache with standardized key: {final_key}"
                    )
                    self._cache_result(final_key, "payee", result)
                else:
                    logger.info(
                        f"{row_info} 📝 Caching payee result with key: {cache_key}"
                    )
                    self._cache_result(cache_key, "payee", result)

            return PayeeResponse(**result)

        except Exception as e:
            logger.error(f"{row_info} ❌ Payee identification failed: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return PayeeResponse(
                payee=clean_desc,
                business_description="Could not determine business details",
                general_category="Unknown",
                confidence="low",
                reasoning=f"Error during identification: {str(e)}",
            )

    def _categorize_business(self, description: str) -> str:
        """Categorize a business based on its description."""
        # Common business categories
        categories = {
            "Food and Dining": [
                "restaurant",
                "cafe",
                "food",
                "dining",
                "coffee",
                "bakery",
            ],
            "Retail Shopping": ["store", "shop", "retail", "market", "mall"],
            "Professional Services": [
                "service",
                "consulting",
                "professional",
                "agency",
                "firm",
            ],
            "Marketing and Advertising": [
                "marketing",
                "advertising",
                "media",
                "promotion",
            ],
            "Travel and Transportation": ["travel", "transport", "airline", "hotel"],
            "Software and Technology": [
                "software",
                "technology",
                "tech",
                "digital",
                "computer",
            ],
            "Healthcare": ["health", "medical", "doctor", "clinic", "hospital"],
            "Financial Services": ["financial", "bank", "insurance", "investment"],
            "Entertainment": ["entertainment", "game", "movie", "theater"],
            "Education and Training": ["education", "training", "school", "university"],
            "Real Estate": ["real estate", "property", "housing", "realty"],
            "Photography and Media": [
                "photo",
                "photography",
                "video",
                "media",
                "studio",
            ],
        }

        description = description.lower()
        for category, keywords in categories.items():
            if any(keyword in description for keyword in keywords):
                return category

        return "Other"

    def _build_category_prompt(
        self,
        description: str,
        payee: str,
        business_description: str = None,
        general_category: str = None,
    ) -> str:
        """Build the prompt for category classification."""
        # Get available categories
        available_categories = self._get_available_categories()

        # Build context information about the transaction
        transaction_context = f"""Transaction Description: {description}
Payee: {payee}"""

        if business_description:
            transaction_context += f"\nBusiness Type: {business_description}"

        if general_category:
            transaction_context += f"\nGeneral Category from Pass 1: {general_category}"

        # Create the prompt based on model type
        if self.model_type == "fast":
            prompt = f"""Analyze this transaction and determine:

{transaction_context}

Available Categories:
{', '.join(available_categories)}

Respond with a JSON object containing:
1. category: The most appropriate category from the list
2. expense_type: "business", "personal", or "mixed"
3. business_percentage: 0-100 (100 for business, 0 for personal, or percentage for mixed)
4. notes: Brief explanation of the categorization"""
        else:
            prompt = f"""Analyze this transaction in detail:

{transaction_context}

Business Context:
{self.business_context}

Available Categories:
{', '.join(available_categories)}

Respond with a JSON object containing:
1. category: The most appropriate category from the list
2. expense_type: "business", "personal", or "mixed"
3. business_percentage: 0-100 (100 for business, 0 for personal, or percentage for mixed)
4. notes: Brief explanation of the categorization
5. confidence: "high", "medium", or "low"
6. detailed_context: Detailed business context and reasoning"""

        return prompt

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
            # Generate cache key using cleaned description and payee
            cache_key = self._get_cache_key(
                self._clean_description(transaction_description),
                self._clean_description(payee) if payee else None,
            )

            # Check cache first unless forced
            if not force_process:
                logger.info(
                    f"{row_info} 🔍 Checking category cache with key: {cache_key}"
                )
                cached_result = self._get_cached_result(cache_key, "category")
                if cached_result:
                    # Validate cached result has required fields
                    required_fields = {
                        "category",
                        "expense_type",
                        "business_percentage",
                        "confidence",
                    }
                    missing_fields = required_fields - set(cached_result.keys())

                    # Use cache if complete and high/medium confidence
                    if not missing_fields and cached_result.get("confidence") in [
                        "high",
                        "medium",
                    ]:
                        logger.info(
                            f"{row_info} ✓ Using cached category: {cached_result['category']} (confidence: {cached_result['confidence']})"
                        )
                        return CategoryResponse(**cached_result)
                    else:
                        logger.info(
                            f"{row_info} ⚠ Invalid or low confidence cache hit, will recompute"
                        )
                else:
                    logger.info(f"{row_info} ⚠ No category cache hit, will compute")

            # Only proceed with OpenAI call if we didn't get a valid cache hit
            logger.info(f"{row_info} 🤖 Getting category from OpenAI")

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

            # Create CategoryResponse object
            category_response = CategoryResponse(**result)

            # Only cache if we have a high/medium confidence result
            if category_response.confidence in ["high", "medium"]:
                logger.info(
                    f"{row_info} 📝 Caching category result with key: {cache_key}"
                )
                self._cache_result(cache_key, "category", category_response.__dict__)

            return category_response

        except Exception as e:
            logger.error(f"{row_info} ❌ Error in category assignment: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _validate_category_response(self, category_info: CategoryResponse) -> bool:
        """Validate category response with stricter business rules."""
        # Special handling for real estate marketing expenses
        if (
            category_info.business_description
            and any(
                kw in category_info.business_description.lower()
                for kw in [
                    "photography",
                    "photo",
                    "virtual tour",
                    "3d tour",
                    "marketing",
                ]
            )
            and "real estate" in category_info.business_description.lower()
        ):
            # Override any previous classification
            category_info.expense_type = "business"
            category_info.business_percentage = 100
            category_info.category = "Advertising"
            category_info.category_confidence = "high"
            category_info.notes = "Real estate photography and marketing services are essential business expenses."
            return True

        # Regular validation rules
        if (
            category_info.expense_type == "business"
            and category_info.category_confidence != "high"
        ):
            # Downgrade to personal if not high confidence
            category_info.expense_type = "personal"
            category_info.business_percentage = 0
            category_info.notes += (
                " [Downgraded to personal due to insufficient confidence]"
            )

        if category_info.business_percentage > 0:
            # List of categories that are typically personal
            personal_categories = [
                "Groceries",
                "Restaurants",
                "Retail",
                "Entertainment",
            ]
            if (
                category_info.category in personal_categories
                and category_info.category_confidence != "high"
            ):
                category_info.business_percentage = 0
                category_info.expense_type = "personal"
                category_info.notes += " [Downgraded to personal due to category type]"

        return True

    def _get_classification(
        self,
        description: str,
        payee: str,
        category: str,
        expense_type: str = "business",
        business_percentage: int = 100,
        business_description: str = None,
        general_category: str = None,
        business_context: str = None,
        force_process: bool = False,
        row_info: str = "",
    ) -> ClassificationResponse:
        """Process a single transaction and classify it for tax purposes."""
        try:
            # Handle personal expenses first
            if expense_type == "personal":
                result = {
                    "tax_category": "Not Applicable",
                    "tax_subcategory": "Personal Expense",
                    "worksheet": "6A",
                    "confidence": "high",
                    "reasoning": "This is a personal expense and not applicable for tax deductions.",
                }
                return ClassificationResponse(**result)

            # Generate cache key consistently using cleaned values and lowercase category
            cache_key = self._get_cache_key(
                self._clean_description(description),
                self._clean_description(payee) if payee else None,
                category.lower() if category else None,
            )
            logger.info(
                f"{row_info} 🔍 Checking tax classification cache with key: {cache_key}"
            )

            # Check cache first unless forced
            if not force_process:
                cached_result = self._get_cached_result(cache_key, "classification")
                if cached_result:
                    # Validate cached result has required fields
                    required_fields = {
                        "tax_category",
                        "tax_subcategory",
                        "worksheet",
                        "confidence",
                    }
                    missing_fields = required_fields - set(cached_result.keys())

                    # Use cache if complete and high/medium confidence
                    if not missing_fields and cached_result.get("confidence") in [
                        "high",
                        "medium",
                    ]:
                        logger.info(
                            f"{row_info} ✓ Using cached tax classification: {cached_result['tax_category']} (confidence: {cached_result['confidence']})"
                        )
                        return ClassificationResponse(**cached_result)
                    else:
                        logger.info(
                            f"{row_info} ⚠ Invalid or low confidence cache hit, will recompute"
                        )
                else:
                    logger.info(
                        f"{row_info} ⚠ No tax classification cache hit, will compute"
                    )

            # Only proceed with OpenAI call if we didn't get a valid cache hit
            logger.info(f"{row_info} 🤖 Getting tax classification from OpenAI")

            # Build prompt for tax classification
            prompt = """Classify this business expense for tax purposes:

Transaction: {description}
Payee: {payee}
Category: {category}
Business Percentage: {business_percentage}%
Business Description: {business_description}
General Category: {general_category}
Business Context: {business_context}

Rules:
1. Use IRS Schedule C (Form 1040) categories
2. Consider the nature of the business expense
3. Assign to most appropriate tax category
4. Provide specific subcategory if applicable
5. Include detailed reasoning for classification

Return a JSON object:
{{
    "tax_category": "IRS Schedule C category",
    "tax_subcategory": "Specific subcategory",
    "worksheet": "6A, Vehicle, or HomeOffice",
    "confidence": "high, medium, or low",
    "reasoning": "detailed explanation"
}}""".format(
                description=description,
                payee=payee,
                category=category,
                business_percentage=business_percentage,
                business_description=business_description or "Not provided",
                general_category=general_category or "Not provided",
                business_context=business_context or "Not provided",
            )

            # Get completion from OpenAI
            response = self.client.chat.completions.create(
                model=self._get_model(),
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a tax classification assistant that provides JSON responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            result = json.loads(response.choices[0].message.content)

            # Validate worksheet value
            if result["worksheet"] not in ["6A", "Vehicle", "HomeOffice"]:
                result["worksheet"] = "6A"
                result["reasoning"] += "\nDefaulted to Form 6A as the worksheet."

            # Only cache if we have a high/medium confidence result
            if result["confidence"] in ["high", "medium"]:
                logger.info(
                    f"{row_info} 📝 Caching tax classification result with key: {cache_key}"
                )
                self._cache_result(cache_key, "classification", result)

            return ClassificationResponse(**result)

        except Exception as e:
            logger.error(f"{row_info} ❌ Error in tax classification: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _get_business_context(self) -> str:
        """Get formatted business context for AI prompts."""
        context = []

        # Add business type and description
        context.append(
            f"Business Type: {self.business_profile.get('business_type', '')}"
        )
        context.append(
            f"Business Description: {self.business_profile.get('business_description', '')}"
        )

        # Add industry insights
        if "industry_insights" in self.business_profile:
            context.append(
                f"Industry Insights: {self.business_profile['industry_insights']}"
            )

        # Add common patterns
        if "common_patterns" in self.business_profile:
            context.append("Common Transaction Patterns:")
            for pattern in self.business_profile["common_patterns"]:
                context.append(f"- {pattern}")

        return "\n".join(context)

    def _get_model(self) -> str:
        """Get the appropriate model based on model type."""
        if self.model_type == "fast":
            return os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini")
        else:
            return os.getenv("OPENAI_MODEL_PRECISE", "o3-mini")

    def test_structured_output(self) -> None:
        """Test that structured outputs are working correctly with a simple schema."""
        test_description = "Walmart Supercenter #1234 - Groceries"

        response = self.client.responses.create(
            model=self._get_model(),
            input=[
                {
                    "role": "system",
                    "content": "You are a transaction classifier. Classify the given transaction.",
                },
                {
                    "role": "user",
                    "content": f"Classify this transaction: {test_description}",
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "test_classification",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "store": {
                                "type": "string",
                                "description": "The store name from the transaction",
                            },
                            "category": {
                                "type": "string",
                                "enum": ["Groceries", "Other"],
                                "description": "The category of the transaction",
                            },
                        },
                        "required": ["store", "category"],
                        "additionalProperties": False,
                    },
                    "strict": True,
                }
            },
        )

        result = json.loads(response.output_text)
        print(f"Test result: {result}")
        return result

    def _determine_worksheet(
        self, transaction: pd.Series, base_category: str
    ) -> WorksheetAssignment:
        """Determine which tax worksheet a transaction belongs to.

        This method analyzes the transaction and its base category to determine:
        1. Which worksheet it belongs to (6A, Vehicle, HomeOffice)
        2. The specific tax category within that worksheet
        3. Whether it needs to be split across worksheets
        """
        # Prepare the prompt with transaction details
        prompt = WorksheetPrompt(
            transaction_description=transaction["description"],
            transaction_amount=transaction["amount"],
            base_category=base_category,
            payee=self._get_existing_payee(transaction["transaction_id"])["payee"],
            date=transaction["transaction_date"].strftime("%Y-%m-%d"),
            business_context=self.business_context,
        )

        # First check if the base category directly maps to a worksheet
        default_worksheet = get_worksheet_for_category(base_category)

        # Prepare the AI prompt
        ai_prompt = f"""Analyze this transaction for tax worksheet assignment:

Transaction Details:
- Description: {prompt.transaction_description}
- Amount: ${prompt.transaction_amount}
- Date: {prompt.date}
- Payee: {prompt.payee}
- Initial Category: {prompt.base_category}

Business Context:
{prompt.business_context}

Available Worksheets:
1. Form 6A (Schedule C) - Main business expenses
2. Vehicle Worksheet - For vehicle-related expenses
3. Home Office Worksheet - For home office expenses

Task:
1. Determine the appropriate worksheet
2. Assign the specific tax category
3. Consider if the expense should be split across worksheets
4. Provide confidence level and reasoning

Special Considerations:
- Vehicle expenses might belong on Vehicle worksheet instead of Form 6A
- Home office expenses should go on Home Office worksheet
- Some expenses might need to be split (e.g., phone bill part business/part home office)

Return a JSON object with:
{
    "worksheet": "6A, Vehicle, or HomeOffice",
    "tax_category": "specific category from the worksheet",
    "tax_subcategory": "subcategory if applicable, otherwise null",
    "line_number": "line number on the form",
    "confidence": "high, medium, or low",
    "reasoning": "detailed explanation",
    "needs_splitting": "true/false",
    "split_details": "null or array of splits if needed"
}"""

        response = self.client.responses.create(
            model=self._get_model(),
            input=[
                {
                    "role": "system",
                    "content": ASSISTANTS_CONFIG["AmeliaAI"]["instructions"],
                },
                {"role": "user", "content": ai_prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "worksheet_assignment",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "worksheet": {
                                "type": "string",
                                "enum": ["6A", "Vehicle", "HomeOffice"],
                                "description": "The assigned worksheet",
                            },
                            "tax_category": {
                                "type": "string",
                                "description": "The specific tax category",
                            },
                            "tax_subcategory": {
                                "type": "string",
                                "description": "Subcategory if applicable",
                            },
                            "line_number": {
                                "type": "string",
                                "description": "Line number on the form",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence in the assignment",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation of the assignment",
                            },
                            "needs_splitting": {
                                "type": "boolean",
                                "description": "Whether the transaction needs to be split",
                            },
                            "split_details": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "worksheet": {"type": "string"},
                                        "tax_category": {"type": "string"},
                                        "amount": {"type": "number"},
                                        "reasoning": {"type": "string"},
                                    },
                                },
                                "description": "Split details if needed",
                            },
                        },
                        "required": [
                            "worksheet",
                            "tax_category",
                            "confidence",
                            "reasoning",
                            "needs_splitting",
                        ],
                    },
                }
            },
        )

        try:
            response_text = response.output_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            result = json.loads(response_text)

            # Validate the tax category exists in the assigned worksheet
            worksheet_cats = TAX_WORKSHEET_CATEGORIES.get(result["worksheet"], {})
            if not any(
                result["tax_category"] in section for section in worksheet_cats.values()
            ):
                # If category not found in assigned worksheet, use default
                result["worksheet"] = default_worksheet
                result["confidence"] = "low"
                result[
                    "reasoning"
                ] += "\nCategory not found in assigned worksheet, using default."

            return WorksheetAssignment(
                worksheet=result["worksheet"],
                tax_category=result["tax_category"],
                tax_subcategory=result.get("tax_subcategory"),
                line_number=result.get(
                    "line_number",
                    get_line_number(result["worksheet"], result["tax_category"]),
                ),
                confidence=result["confidence"],
                reasoning=result["reasoning"],
                needs_splitting=result["needs_splitting"],
                split_details=result.get("split_details"),
            )

        except Exception as e:
            logger.error(f"Error determining worksheet: {str(e)}")
            # Fall back to default worksheet based on category
            return WorksheetAssignment(
                worksheet=default_worksheet,
                tax_category=base_category,
                tax_subcategory=None,
                line_number=get_line_number(default_worksheet, base_category),
                confidence="low",
                reasoning=f"Error during processing: {str(e)}",
                needs_splitting=False,
                split_details=None,
            )

    def _get_available_categories(self) -> List[str]:
        """Get all available categories (standard + custom)."""
        # Define base business categories
        base_business_categories = [
            "Office Supplies",
            "Software and Technology",
            "Professional Services",
            "Marketing and Advertising",
            "Travel Expenses",
            "Meals and Entertainment",
            "Vehicle Expenses",
            "Equipment and Furniture",
            "Training and Education",
            "Insurance",
            "Rent and Utilities",
            "Maintenance and Repairs",
            "Banking and Financial Fees",
            "Shipping and Postage",
            "Employee Benefits",
            "Contract Services",
            "Licenses and Permits",
            "Other Business Expenses",
        ]

        # Define common personal expense categories
        personal_categories = [
            "Groceries",
            "Dining Out",
            "Personal Shopping",
            "Entertainment",
            "Healthcare",
            "Personal Services",
            "Housing",
            "Utilities (Personal)",
            "Transportation",
            "Education",
            "Travel (Personal)",
            "Home Improvement",
            "Subscriptions",
            "Childcare",
            "Pet Expenses",
            "Hobbies",
            "Other Personal Expenses",
        ]

        # Get client's custom categories
        client_categories = self.db.get_client_categories(self.client_name)
        custom_categories = [cat["category_name"] for cat in client_categories]

        # Combine all categories
        return base_business_categories + personal_categories + custom_categories

    def process_single_row(
        self,
        transactions_df: pd.DataFrame,
        row_number: int,
        force_process: bool = False,
    ) -> None:
        """Process a single transaction through all passes.

        Args:
            transactions_df: DataFrame containing all transactions
            row_number: The row number to process (1-based index)
            force_process: Whether to force processing even if already processed
        """
        if row_number < 1 or row_number > len(transactions_df):
            raise ValueError(f"Row number must be between 1 and {len(transactions_df)}")

        # Convert to 0-based index
        idx = row_number - 1
        transaction = transactions_df.iloc[idx]

        logger.info(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")
        logger.info(
            f"{Fore.GREEN}▶ Processing single transaction (Row {row_number}){Style.RESET_ALL}"
        )
        logger.info(f"  • Transaction: {transaction['description']}")
        logger.info(f"  • Amount: ${transaction['amount']}")
        logger.info(f"  • Date: {transaction['transaction_date']}")
        logger.info(f"{Fore.GREEN}{'='*80}{Style.RESET_ALL}\n")

        try:
            # Pass 1: Payee identification
            logger.info(f"{Fore.GREEN}▶ PASS 1: Payee Identification{Style.RESET_ALL}")
            payee_info = self._get_payee(
                transaction["description"],
                row_info=f"[Row {row_number}]",
                force_process=force_process,
            )

            # Update transaction with payee info
            update_data = {
                "client_id": self.db.get_client_id(self.client_name),
                "payee": payee_info.payee,
                "payee_confidence": payee_info.confidence,
                "payee_reasoning": payee_info.reasoning,
                "business_description": payee_info.business_description,
                "general_category": payee_info.general_category,
            }
            self.db.update_transaction_classification(
                transaction["transaction_id"], update_data
            )

            # Update status
            self.db.update_transaction_status(
                transaction["transaction_id"],
                {
                    "client_id": self.db.get_client_id(self.client_name),
                    "pass_1_status": "completed",
                    "pass_1_error": None,
                    "pass_1_processed_at": datetime.now(),
                },
            )

            logger.info(
                f"{Fore.GREEN}✓ Pass 1 complete: {payee_info.payee} ({payee_info.confidence}){Style.RESET_ALL}"
            )

            # Pass 2: Category assignment
            logger.info(f"{Fore.GREEN}▶ PASS 2: Category Assignment{Style.RESET_ALL}")
            category_info = self._get_category(
                transaction["description"],
                transaction["amount"],
                transaction["transaction_date"].strftime("%Y-%m-%d"),
                payee=payee_info.payee,
                business_description=payee_info.business_description,
                general_category=payee_info.general_category,
                force_process=force_process,
                row_info=f"[Row {row_number}]",
            )

            # Update transaction with category info
            update_data = {
                "client_id": self.db.get_client_id(self.client_name),
                "category": str(category_info.category),
                "category_confidence": str(category_info.confidence),
                "category_reasoning": str(category_info.notes),
                "expense_type": str(category_info.expense_type),
                "business_percentage": int(category_info.business_percentage),
                "business_context": str(category_info.detailed_context or ""),
                "classification": str(
                    "Business"
                    if category_info.expense_type == "business"
                    else (
                        "Personal"
                        if category_info.expense_type == "personal"
                        else "Unclassified"
                    )
                ),
                "classification_confidence": str(category_info.confidence),
            }
            self.db.update_transaction_classification(
                transaction["transaction_id"], update_data
            )

            # Update status
            self.db.update_transaction_status(
                transaction["transaction_id"],
                {
                    "client_id": self.db.get_client_id(self.client_name),
                    "pass_2_status": "completed",
                    "pass_2_error": None,
                    "pass_2_processed_at": datetime.now(),
                },
            )

            logger.info(
                f"{Fore.GREEN}✓ Pass 2 complete: {category_info.category} ({category_info.expense_type}){Style.RESET_ALL}"
            )

            # Pass 3: Tax Classification
            logger.info(f"{Fore.GREEN}▶ PASS 3: Tax Classification{Style.RESET_ALL}")

            # Skip personal expenses from detailed tax classification
            if category_info.expense_type == "personal":
                logger.info(
                    f"{Fore.GREEN}ℹ Personal expense, setting minimal tax classification{Style.RESET_ALL}"
                )
                classification_info = ClassificationResponse(
                    tax_category="Not Applicable",
                    tax_subcategory="Personal Expense",
                    worksheet="6A",
                    confidence="high",
                    reasoning="This is a personal expense and not applicable for tax deductions.",
                )
            else:
                # Get classification info from LLM
                logger.info(
                    f"{Fore.GREEN}🤖 Getting tax classification for: {category_info.category}{Style.RESET_ALL}"
                )
                classification_info = self._get_classification(
                    transaction["description"],
                    payee_info.payee,
                    category_info.category,
                    category_info.expense_type,
                    category_info.business_percentage,
                    payee_info.business_description,
                    payee_info.general_category,
                    category_info.detailed_context,
                    force_process=force_process,
                    row_info=f"[Row {row_number}]",
                )

            # Update transaction with classification info
            update_data = {
                "client_id": self.db.get_client_id(self.client_name),
                "tax_category": classification_info.tax_category,
                "tax_subcategory": classification_info.tax_subcategory,
                "worksheet": classification_info.worksheet,
                "classification_confidence": classification_info.confidence,
                "classification_reasoning": classification_info.reasoning,
            }
            self.db.update_transaction_classification(
                transaction["transaction_id"], update_data
            )

            # Update status
            self.db.update_transaction_status(
                transaction["transaction_id"],
                {
                    "client_id": self.db.get_client_id(self.client_name),
                    "pass_3_status": "completed",
                    "pass_3_error": None,
                    "pass_3_processed_at": datetime.now(),
                },
            )

            logger.info(
                f"{Fore.GREEN}✓ Pass 3 complete: {classification_info.tax_category} (worksheet: {classification_info.worksheet}){Style.RESET_ALL}"
            )

        except Exception as e:
            error_message = f"Error processing transaction {row_number}: {str(e)}"
            logger.error(f"{Fore.RED}❌ {error_message}{Style.RESET_ALL}")
            raise

        logger.info(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")
        logger.info(
            f"{Fore.GREEN}▶ Single Transaction Processing Complete!{Style.RESET_ALL}"
        )
        logger.info(f"{Fore.GREEN}{'='*80}{Style.RESET_ALL}\n")

    def _get_llm_response(self, prompt: str) -> str:
        """Get a response from the LLM model.

        Args:
            prompt: The prompt to send to the model

        Returns:
            The model's response as a string
        """
        try:
            # Check if prompt contains JSON request
            needs_json = "Return JSON" in prompt or "JSON response" in prompt

            response = self.client.chat.completions.create(
                model=self._get_model(),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a transaction analysis assistant that provides detailed responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=500,
                response_format={"type": "json_object"} if needs_json else None,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error getting LLM response: {str(e)}")
            raise


@dataclass
class ClassificationResponse:
    """Response from classification step."""

    tax_category: str
    tax_subcategory: str = ""
    worksheet: str = "6A"
    confidence: str = "medium"
    reasoning: str = ""
