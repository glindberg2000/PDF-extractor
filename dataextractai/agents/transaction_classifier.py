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
from tools.vendor_lookup import lookup_vendor_info
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
    def __init__(self, client_name: str, model_type: str = "fast"):
        """Initialize the transaction classifier.

        Args:
            client_name: Name of the client whose transactions to classify
            model_type: Type of model to use ("fast" or "precise")
        """
        self.client_name = client_name
        self.client = OpenAI()
        self.profile_manager = ClientProfileManager(client_name)
        self.business_profile = self.profile_manager._load_profile()
        self.model_type = model_type
        self.db = ClientDB()

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

    def _get_cache_key(
        self,
        description: str,
        payee: Optional[str] = None,
        category: Optional[str] = None,
    ) -> str:
        """Generate a cache key for a transaction."""
        # Normalize the description (remove extra spaces, convert to lowercase)
        normalized_desc = " ".join(description.lower().split())

        # Create a unique key based on the transaction details
        key_parts = [normalized_desc]
        if payee:
            key_parts.append(payee.lower())
        if category:
            key_parts.append(category.lower())

        return "|".join(key_parts)

    def _get_cached_result(self, cache_key: str, pass_type: str) -> Optional[Dict]:
        """Get a cached result from the database."""
        with sqlite3.connect(self.db.db_path) as conn:
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
                    f"{Fore.CYAN}[CACHE HIT] Found cached {pass_type} result for: {cache_key.split('|')[0][:40]}...{Style.RESET_ALL}"
                )
                cached = json.loads(result[0])

                # Handle legacy cache format for category responses
                if pass_type == "category":
                    # Map old fields to new structure
                    return {
                        "category": cached.get("category", ""),
                        "expense_type": cached.get("expense_type", "personal"),
                        "business_percentage": int(
                            cached.get("business_percentage", 0)
                        ),
                        "notes": cached.get(
                            "reasoning", ""
                        ),  # Map old reasoning to notes
                        "confidence": cached.get("confidence", "medium"),
                        "detailed_context": cached.get(
                            "business_context", ""
                        ),  # Map old business_context to detailed_context
                    }
                return cached
        return None

    def _cache_result(self, cache_key: str, pass_type: str, result: Dict) -> None:
        """Save a result to the database cache."""
        client_id = self.db.get_client_id(self.client_name)
        with sqlite3.connect(self.db.db_path) as conn:
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

            try:
                # Check if transaction is already fully processed
                if not force_process:
                    status = self.db.get_transaction_status(
                        transaction["transaction_id"]
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
                        transaction["description"], row_number, force_process
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
                            f"[Row {row_number}] ⚠ No payee found from pass 1, skipping pass 2"
                        )
                        continue

                    # Check cache for category
                    cache_key = self._get_cache_key(
                        transaction["description"], existing["payee"]
                    )
                    cached_category = self._get_cached_result(cache_key, "category")

                    if cached_category and not force_process:
                        logger.info(
                            f"[Row {row_number}] ✓ Using cached category: {cached_category['category']} (confidence: {cached_category['confidence']})"
                        )
                        category_info = CategoryResponse(**cached_category)
                        cache_hit_count[2] += 1
                    else:
                        # Get category info from LLM
                        logger.info(
                            f"[Row {row_number}] 🤖 Getting category for: {existing['payee']}"
                        )
                        category_info = self._get_category(
                            transaction["description"],
                            transaction["amount"],
                            transaction["transaction_date"].strftime("%Y-%m-%d"),
                        )
                        logger.info(
                            f"[Row {row_number}] ✓ Category assigned: {category_info.category} (confidence: {category_info.confidence})"
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
                            "classification_confidence": str(category_info.confidence),
                        }

                        # Log what we're updating
                        logger.info(
                            f"[Row {row_number}] Updating transaction {transaction['transaction_id']} with:"
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
                            f"[Row {row_number}] ⚠ No category found from pass 2, skipping pass 3"
                        )
                        continue

                    # Skip personal expenses from detailed tax classification
                    if existing.get("expense_type") == "personal":
                        logger.info(
                            f"[Row {row_number}] ℹ Personal expense, setting minimal tax classification"
                        )
                        classification_info = ClassificationResponse(
                            tax_category="Not Applicable",
                            tax_subcategory="Personal Expense",
                            worksheet="None",
                            confidence="high",
                            reasoning="This is a personal expense and not applicable for tax deductions.",
                        )
                        cache_hit_count[3] += 1
                    else:
                        # Check cache for classification
                        cache_key = self._get_cache_key(
                            transaction["description"],
                            existing["payee"],
                            existing["base_category"],
                        )
                        cached_classification = self._get_cached_result(
                            cache_key, "classification"
                        )

                        if cached_classification and not force_process:
                            logger.info(
                                f"[Row {row_number}] ✓ Using cached tax classification: {cached_classification.get('tax_category', 'Unknown')}"
                            )
                            classification_info = ClassificationResponse(
                                **cached_classification
                            )
                            cache_hit_count[3] += 1
                        else:
                            # Get business percentage
                            business_percentage = existing.get(
                                "business_percentage",
                                (
                                    100
                                    if existing.get("expense_type") == "business"
                                    else 0
                                ),
                            )

                            # Get classification info from LLM
                            logger.info(
                                f"[Row {row_number}] 🤖 Getting tax classification for: {existing['base_category']}"
                            )
                            classification_info = self._get_classification(
                                transaction["description"],
                                existing["payee"],
                                existing["base_category"],
                                existing.get("expense_type", "business"),
                                business_percentage,
                                existing.get("business_description"),
                                existing.get("general_category"),
                                existing.get("business_context"),
                                force_process,
                            )
                            logger.info(
                                f"[Row {row_number}] ✓ Tax classification: {classification_info.tax_category} (confidence: {classification_info.confidence})"
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
                        and not cached_classification
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
                error_message = f"Error processing transaction {row_number}: {str(e)}"
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
        logger.info(f"{Fore.GREEN}▶ Transaction Processing Summary{Style.RESET_ALL}")
        for pass_num in range(resume_from_pass, 4):
            if pass_num <= 3:
                logger.info(f"  • Pass {pass_num} ({pass_desc.get(pass_num)})")
                logger.info(f"    - Processed: {processed_count.get(pass_num, 0)}")
                logger.info(f"    - Skipped: {skipped_count.get(pass_num, 0)}")
                logger.info(f"    - Cache hits: {cache_hit_count.get(pass_num, 0)}")
                logger.info(f"    - Errors: {error_count.get(pass_num, 0)}")

        logger.info(f"{Fore.GREEN}{'='*80}{Style.RESET_ALL}\n")
        logger.info(f"{Fore.GREEN}Transaction processing complete!{Style.RESET_ALL}")

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

    def _get_payee(
        self,
        description: str,
        row_number: Optional[int] = None,
        force_process: bool = False,
    ) -> PayeeResponse:
        """Process a single description to identify payee.

        Args:
            description: The transaction description to analyze
            row_number: Optional row number for logging context
            force_process: Whether to do fresh lookups for missing fields
        """
        row_info = f"[Row {row_number}]" if row_number is not None else ""

        # Create a visually distinct separator for this transaction
        logger.info(
            f"{row_info} {Fore.CYAN}Processing payee for: {description}{Style.RESET_ALL}"
        )

        cache_key = self._get_cache_key(description)
        cached_result = self._get_cached_result(cache_key, "payee")

        # Check if we have a valid cache hit
        if cached_result:
            result = PayeeResponse(**cached_result)

            # If not forcing process and we have high confidence or enriched data, use cache as is
            if not force_process and (
                result.confidence == "high"
                or "Enriched with business information:" in result.reasoning
            ):
                logger.info(
                    f"{row_info} {Fore.CYAN}✓ Using cached payee: {result.payee} ({result.confidence} confidence){Style.RESET_ALL}"
                )
                return result

            # If forcing process or low confidence, check for missing fields
            missing_fields = []
            if not result.business_description:
                missing_fields.append("business_description")
            if not result.general_category:
                missing_fields.append("general_category")

            # If we have all fields and high confidence, use cache
            if not missing_fields and result.confidence == "high":
                logger.info(
                    f"{row_info} {Fore.CYAN}✓ Using complete cached payee: {result.payee} ({result.confidence} confidence){Style.RESET_ALL}"
                )
                return result

            # If only missing some fields, log what we're updating
            if missing_fields:
                logger.info(
                    f"{row_info} {Fore.YELLOW}⚠ Cache hit but missing fields: {', '.join(missing_fields)}. Will update...{Style.RESET_ALL}"
                )
            else:
                logger.info(
                    f"{row_info} {Fore.YELLOW}⚠ Low confidence cache hit ({result.confidence}), will try to improve...{Style.RESET_ALL}"
                )

        # Get initial AI identification
        logger.info(f"{row_info} 🤖 Getting identification from LLM...")
        prompt = f"""Analyze this transaction description to identify the payee (merchant or recipient of payment).

Transaction Description: {description}

Business Context:
{self.business_context}

Provide the following information:
1. The most likely payee name (merchant or recipient)
2. A brief description of what type of business this payee is
3. A general expense category for this transaction

Format your response as a JSON object with these fields:
- payee: The name of the payee/merchant
- business_description: A clear, concise description of what type of business this payee is
- general_category: A general expense category for this transaction
- confidence: Your confidence level (high, medium, low)
- reasoning: Your explanation for this identification

Some examples of general expense categories:
- Food and Dining
- Office Supplies
- Professional Services
- Marketing and Advertising
- Travel and Transportation
- Software and Technology
- Rent and Utilities
- Insurance
- Education and Training
- Retail Shopping
- Entertainment
- Financial Services
- Healthcare
- Other

NOTES:
- For common merchants, identify the brand name (not the payment processor)
- For online merchants, include what they sell if possible
- If the payee is ambiguous, explain why in your reasoning
"""

        response = self.client.responses.create(
            model=self._get_model(),
            input=[
                {
                    "role": "system",
                    "content": ASSISTANTS_CONFIG["AmeliaAI"]["instructions"],
                },
                {"role": "user", "content": prompt},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "payee_response",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "payee": {
                                "type": "string",
                                "description": "The identified payee/merchant name",
                            },
                            "business_description": {
                                "type": "string",
                                "description": "A brief description of what type of business this payee is",
                            },
                            "general_category": {
                                "type": "string",
                                "description": "A general expense category for this transaction",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence level in the identification",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation of the identification",
                            },
                        },
                        "required": [
                            "payee",
                            "business_description",
                            "general_category",
                            "confidence",
                            "reasoning",
                        ],
                        "additionalProperties": False,
                    },
                    "strict": True,
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
            new_response = PayeeResponse(**result)

            # If we had a cached result, merge the new fields with existing data
            if cached_result:
                cached = PayeeResponse(**cached_result)
                # Keep the cached payee and confidence if they were high confidence
                if cached.confidence == "high":
                    result["payee"] = cached.payee
                    result["confidence"] = cached.confidence
                # Update only the missing or low confidence fields
                if not cached.business_description:
                    result["business_description"] = new_response.business_description
                if not cached.general_category:
                    result["general_category"] = new_response.general_category
                # Combine reasoning
                result["reasoning"] = (
                    f"Original identification: {cached.reasoning}\nUpdated with: {new_response.reasoning}"
                )

            logger.info(
                f"{row_info} 🤖 {'Updated' if cached_result else 'New'} payee: {result['payee']} ({result['confidence']} confidence)"
            )

            if "business_description" in result:
                logger.info(
                    f"{row_info} 📋 Business type: {result['business_description']}"
                )

            if "general_category" in result:
                logger.info(
                    f"{row_info} 🏷️ General category: {result['general_category']}"
                )

            # Cache the result with all fields
            self._cache_result(
                cache_key,
                "payee",
                result,
            )

            logger.info(
                f"{row_info} {Fore.GREEN}✓ FINAL PAYEE: {result['payee']} ({result['confidence']} confidence){Style.RESET_ALL}"
            )

            return PayeeResponse(**result)

        except Exception as e:
            logger.error(f"{row_info} {Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
            return PayeeResponse(
                payee="Unknown Payee",
                confidence="low",
                reasoning=f"Error: {str(e)}",
                business_description="",
                general_category="",
            )

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
    ) -> CategoryResponse:
        """Get the category for a transaction."""
        # Default to personal unless strong business case
        default_classification = {
            "category": "Uncategorized",
            "expense_type": "personal",
            "business_percentage": 0,
            "category_confidence": "low",
            "notes": "Default personal classification",
        }

        # Build a more conservative prompt
        prompt = f"""Classify this transaction with an IRS-audit mindset. Default to personal unless there is clear business justification.
Transaction: {transaction_description}
Amount: ${amount}
Date: {date}

Business Profile: Real estate professional

Rules:
1. Default to personal (0% business) unless clear business connection
2. Groceries, restaurants, and retail stores are personal by default
3. Only classify as business if:
   - Direct real estate expenses (property maintenance, utilities for properties)
   - Clear professional services (legal, accounting)
   - Documented business meetings or travel
4. Mixed expenses need strong justification and documentation
5. Mark confidence as:
   - high: Clear business purpose with documentation
   - medium: Likely business but needs verification
   - low: Uncertain or personal by default

Respond in JSON format:
{{
    "category": "Category name",
    "expense_type": "business|personal|mixed",
    "business_percentage": 0-100,
    "category_confidence": "high|medium|low",
    "notes": "Detailed reasoning including what documentation would be needed for IRS"
}}"""

        try:
            # Get completion from OpenAI
            response = self.client.chat.completions.create(
                model=self._get_model(), messages=[{"role": "user", "content": prompt}]
            )

            # Extract and parse the response
            response_text = response.choices[0].message.content.strip()
            # Remove any markdown formatting
            response_text = response_text.replace("```json\n", "").replace("\n```", "")

            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Raw response: {response_text}")
                # Attempt to extract JSON from the response
                match = re.search(r"\{.*\}", response_text, re.DOTALL)
                if match:
                    try:
                        result = json.loads(match.group(0))
                    except json.JSONDecodeError:
                        raise
                else:
                    raise

            # Validate and set defaults for required fields
            result = {
                "category": str(result.get("category", "Other Business Expenses")),
                "expense_type": str(result.get("expense_type", "personal")),
                "business_percentage": int(result.get("business_percentage", 0)),
                "notes": str(result.get("notes", "")),
                "confidence": str(result.get("confidence", "medium")),
                "detailed_context": str(result.get("detailed_context", "")),
            }

            # Ensure consistent business logic
            if result["expense_type"] == "business":
                result["business_percentage"] = 100
            elif result["expense_type"] == "personal":
                result["business_percentage"] = 0
            elif result["expense_type"] == "mixed":
                if (
                    result["business_percentage"] <= 0
                    or result["business_percentage"] >= 100
                ):
                    result["business_percentage"] = 50

            # Create CategoryResponse object
            category_response = CategoryResponse(**result)

            # Cache the result
            self._cache_result(
                self._get_cache_key(transaction_description),
                "category",
                category_response.__dict__,
            )

            return category_response

        except Exception as e:
            logger.error(f"Error in _get_category: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def _validate_category_response(self, category_info: CategoryResponse) -> bool:
        """Validate category response with stricter business rules."""
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
    ) -> ClassificationResponse:
        """Process a single transaction and classify it for tax purposes.

        Args:
            description: The transaction description.
            payee: The identified payee name.
            category: The assigned base category.
            expense_type: The type of expense (business, personal, mixed).
            business_percentage: The business use percentage for mixed expenses.
            business_description: Description of the payee's business (optional).
            general_category: General expense category identified (optional).
            business_context: Business context for this transaction (optional).
            force_process: Whether to bypass cache and force processing.

        Returns:
            A ClassificationResponse containing the tax information.
        """
        try:
            # Get business profile if available
            profile_data = None
            try:
                profile_data = self.db.get_business_profile(self.client_name)
                if profile_data:
                    profile_data = json.loads(profile_data["profile_data"])
            except:
                logger.warning(
                    f"⚠ Failed to load business profile for {self.client_name}"
                )

            # Skip personal expenses
            if expense_type == "personal":
                return ClassificationResponse(
                    tax_category="Not Applicable",
                    tax_subcategory="Personal Expense",
                    worksheet="None",
                    confidence="high",
                    reasoning="This is a personal expense and not applicable for tax deductions.",
                )

            # Check cache for classification if not forcing process
            cache_key = self._get_cache_key(description, payee, category)
            if not force_process:
                cached_result = self._get_cached_result(cache_key, "classification")
                if cached_result:
                    logger.info(
                        f"✓ Using cached tax classification: {cached_result.get('tax_category', 'Unknown')}"
                    )
                    return ClassificationResponse(**cached_result)

            # Define context for the AI model
            transaction_context = f"Transaction: {description}\nPayee: {payee}\nCategory: {category}\nExpense Type: {expense_type}\nBusiness Percentage: {business_percentage}%"

            # Add business description if available
            if business_description:
                transaction_context += f"\nBusiness Description: {business_description}"

            # Add general category if available
            if general_category:
                transaction_context += f"\nGeneral Category: {general_category}"

            # Add business context if available
            if business_context:
                transaction_context += f"\nBusiness Context: {business_context}"

            # Add business profile context if available
            business_context_prompt = ""
            if profile_data:
                business_context_prompt = f"""
Business Information:
- Business Name: {profile_data.get('business_name', 'N/A')}
- Business Type: {profile_data.get('business_type', 'N/A')}
- Tax Entity Type: {profile_data.get('tax_entity_type', 'N/A')}"""

                # Add Schedule 6A categories if available
                if profile_data.get("schedule_6a_categories"):
                    business_context_prompt += (
                        "\n\nApplicable Schedule 6A Categories for this business:"
                    )
                    for sch_cat in profile_data.get("schedule_6a_categories", []):
                        business_context_prompt += f"\n- {sch_cat}"
                else:
                    business_context_prompt += "\n\nAssume this is a real estate investor or property manager for classification purposes."

            # Set up the initial prompt
            prompt = f"""You are a tax classification expert specializing in real estate investing and small business expense categorization according to IRS rules. 

{business_context_prompt}

TASK:
Analyze the following transaction and provide accurate tax classification according to IRS Schedule 6A for real estate investors.

{transaction_context}

INSTRUCTIONS:
1. Determine the most appropriate tax category for this expense based on IRS Schedule 6A.
2. For each expense, determine which worksheet it belongs to: "6A" (general expenses), "Vehicle" (auto expenses), or "HomeOffice" (home office expenses).
3. If this is not a valid business expense, explain why.
4. For business expenses, provide a confidence level and detailed reasoning.
5. For mixed-use expenses, make sure the business percentage is appropriate based on the nature of the expense.

Response must follow this JSON format:
{{
  "tax_category": "<primary tax category - use one of the Schedule 6A categories or 'Not Deductible' if not tax-deductible>",
  "tax_subcategory": "<sub-category or specific expense type>",
  "worksheet": "<'6A', 'Vehicle', or 'HomeOffice'>",
  "confidence": "<'high', 'medium', or 'low'>",
  "reasoning": "<detailed explanation justifying this classification, including any relevant tax rules or considerations>"
}}

Valid Schedule 6A categories include: "Advertising", "Car and truck expenses", "Commissions and fees", "Contract labor", "Depletion", "Depreciation", "Insurance", "Interest", "Legal and professional services", "Office expenses", "Pension and profit-sharing plans", "Rent or lease", "Repairs and maintenance", "Supplies", "Taxes and licenses", "Travel", "Meals", "Utilities", "Wages", "Other expenses", "Not Deductible".
"""

            # User completions API
            result = self.client.chat.completions.create(
                model=self._get_model(),
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": "You are a tax classification assistant that provides JSON responses.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )

            response_content = result.choices[0].message.content
            data = json.loads(response_content)

            # Map to expected fields and ensure tax_category exists
            tax_category = data.get("tax_category", "Unknown")
            tax_subcategory = data.get("tax_subcategory", "")
            worksheet = data.get("worksheet", "6A")
            confidence = data.get("confidence", "medium")
            reasoning = data.get("reasoning", "")

            # Validate the tax category against Schedule 6A categories
            valid_categories = [
                "Advertising",
                "Car and truck expenses",
                "Commissions and fees",
                "Contract labor",
                "Depletion",
                "Depreciation",
                "Insurance",
                "Interest",
                "Legal and professional services",
                "Office expenses",
                "Pension and profit-sharing plans",
                "Rent or lease",
                "Repairs and maintenance",
                "Supplies",
                "Taxes and licenses",
                "Travel",
                "Meals",
                "Utilities",
                "Wages",
                "Other expenses",
                "Not Deductible",
            ]

            if tax_category not in valid_categories:
                # Try to find the closest match
                closest_match = difflib.get_close_matches(
                    tax_category, valid_categories, n=1
                )
                if closest_match:
                    logger.warning(
                        f"⚠ Tax category '{tax_category}' not recognized, using closest match: '{closest_match[0]}'"
                    )
                    tax_category = closest_match[0]
                else:
                    logger.warning(
                        f"⚠ Tax category '{tax_category}' not recognized, using 'Other expenses'"
                    )
                    tax_category = "Other expenses"

            # Validate worksheet values
            valid_worksheets = ["6A", "Vehicle", "HomeOffice"]
            if worksheet not in valid_worksheets:
                logger.warning(f"⚠ Worksheet '{worksheet}' not recognized, using '6A'")
                worksheet = "6A"

            return ClassificationResponse(
                tax_category=tax_category,
                tax_subcategory=tax_subcategory,
                worksheet=worksheet,
                confidence=confidence,
                reasoning=reasoning,
            )

        except Exception as e:
            logger.error(f"❌ Error classifying transaction: {str(e)}")
            traceback.print_exc()
            return ClassificationResponse(
                tax_category="Classification Failed",
                tax_subcategory="Error",
                worksheet="6A",
                confidence="low",
                reasoning=f"Error occurred during classification: {str(e)}",
            )

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


@dataclass
class ClassificationResponse:
    """Response from classification step."""

    tax_category: str
    tax_subcategory: str = ""
    worksheet: str = "6A"
    confidence: str = "medium"
    reasoning: str = ""
