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
                return json.loads(result[0])
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
                    payee_info = self._get_payee(transaction["description"], row_number)

                    # Extract business description and general category from reasoning if available
                    business_description = None
                    general_category = None

                    # If the response was cached and has these fields
                    cache_key = self._get_cache_key(transaction["description"])
                    cached_result = self._get_cached_result(cache_key, "payee")
                    if cached_result:
                        business_description = cached_result.get("business_description")
                        general_category = cached_result.get("general_category")

                    # If not in cache, try to extract from reasoning
                    if (
                        not business_description
                        and "business description:" in payee_info.reasoning.lower()
                    ):
                        try:
                            desc_lines = [
                                line
                                for line in payee_info.reasoning.split("\n")
                                if "business description:" in line.lower()
                            ]
                            if desc_lines:
                                business_description = (
                                    desc_lines[0].split(":", 1)[1].strip()
                                )
                        except:
                            pass

                    if (
                        not general_category
                        and "general category:" in payee_info.reasoning.lower()
                    ):
                        try:
                            cat_lines = [
                                line
                                for line in payee_info.reasoning.split("\n")
                                if "general category:" in line.lower()
                            ]
                            if cat_lines:
                                general_category = cat_lines[0].split(":", 1)[1].strip()
                        except:
                            pass

                    # Update transaction with payee info
                    update_data = {
                        "client_id": self.db.get_client_id(self.client_name),
                        "payee": payee_info.payee,
                        "payee_confidence": payee_info.confidence,
                        "payee_reasoning": payee_info.reasoning,
                    }

                    # Add the new fields if available
                    if business_description:
                        update_data["business_description"] = business_description
                        logger.info(
                            f"[Row {row_number}] Business description: {business_description}"
                        )

                    if general_category:
                        update_data["general_category"] = general_category
                        logger.info(
                            f"[Row {row_number}] General category: {general_category}"
                        )

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
                        f"{Fore.GREEN}✓ Pass 1 complete: {payee_info.payee} ({payee_info.confidence} confidence){Style.RESET_ALL}"
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
                            existing["payee"],
                            existing.get("business_description"),
                            existing.get("general_category"),
                        )
                        logger.info(
                            f"[Row {row_number}] ✓ Category assigned: {category_info.category} (confidence: {category_info.confidence})"
                        )

                    # Extract expense_type from reasoning
                    expense_type = "personal"  # Default to personal
                    business_percentage = 0  # Default to 0%
                    business_context = ""  # Default to empty

                    if "Expense type: business" in category_info.reasoning:
                        expense_type = "business"
                        business_percentage = 100  # Default for business
                    elif "Expense type: mixed" in category_info.reasoning:
                        expense_type = "mixed"
                        # Try to extract percentage
                        try:
                            if "Business percentage:" in category_info.reasoning:
                                percentage_line = [
                                    line
                                    for line in category_info.reasoning.split("\n")
                                    if "Business percentage:" in line
                                ][0]
                                percentage_str = (
                                    percentage_line.split(":", 1)[1].strip().rstrip("%")
                                )
                                business_percentage = int(percentage_str)
                            elif (
                                "business percentage:"
                                in category_info.reasoning.lower()
                            ):
                                percentage_line = [
                                    line
                                    for line in category_info.reasoning.split("\n")
                                    if "business percentage:" in line.lower()
                                ][0]
                                percentage_str = (
                                    percentage_line.split(":", 1)[1].strip().rstrip("%")
                                )
                                business_percentage = int(percentage_str)
                        except:
                            # If extraction fails, use 50% as default for mixed
                            business_percentage = 50

                    # Try to extract business_context if available
                    if "Business context:" in category_info.reasoning:
                        try:
                            context_start = category_info.reasoning.find(
                                "Business context:"
                            )
                            if context_start > 0:
                                context_part = category_info.reasoning[
                                    context_start + 17 :
                                ]
                                # Extract until next double newline or end
                                end_pos = context_part.find("\n\n")
                                if end_pos > 0:
                                    business_context = context_part[:end_pos].strip()
                                else:
                                    business_context = context_part.strip()
                        except:
                            pass

                    logger.info(f"[Row {row_number}] • Expense type: {expense_type}")
                    logger.info(
                        f"[Row {row_number}] • Business percentage: {business_percentage}%"
                    )
                    if business_context:
                        logger.info(
                            f"[Row {row_number}] • Business context: {business_context[:100]}..."
                        )

                    # Update transaction with category info
                    update_data = {
                        "client_id": self.db.get_client_id(self.client_name),
                        "base_category": category_info.category,
                        "category_confidence": category_info.confidence,
                        "category_reasoning": category_info.reasoning,
                        "expense_type": expense_type,
                        "business_percentage": business_percentage,
                    }

                    if business_context:
                        update_data["business_context"] = business_context

                    self.db.update_transaction_classification(
                        transaction["transaction_id"], update_data
                    )

                    # Cache the result with expense_type
                    if not cached_category:
                        cache_data = {
                            "category": category_info.category,
                            "confidence": category_info.confidence,
                            "reasoning": category_info.reasoning,
                            "expense_type": expense_type,
                            "business_percentage": business_percentage,
                        }

                        if business_context:
                            cache_data["business_context"] = business_context

                        self._cache_result(cache_key, "category", cache_data)

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
                        f"{Fore.GREEN}✓ Pass 2 complete: {category_info.category} ({expense_type}){Style.RESET_ALL}"
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
        self, description: str, row_number: Optional[int] = None
    ) -> PayeeResponse:
        """Process a single description to identify payee.

        Args:
            description: The transaction description to analyze
            row_number: Optional row number for logging context
        """
        row_info = f"[Row {row_number}]" if row_number is not None else ""

        # Create a visually distinct separator for this transaction
        logger.info(
            f"{row_info} {Fore.CYAN}Processing payee for: {description}{Style.RESET_ALL}"
        )

        cache_key = self._get_cache_key(description)

        # Check cache first
        cached_result = self._get_cached_result(cache_key, "payee")
        if cached_result:
            # Parse the cached result
            result = PayeeResponse(**cached_result)

            # Only use cache if:
            # 1. It's a high confidence result, OR
            # 2. It's been enriched with Brave Search before (indicated by enrichment info in reasoning)
            if (
                result.confidence == "high"
                or "Enriched with business information:" in result.reasoning
            ):
                logger.info(
                    f"{row_info} {Fore.CYAN}✓ Using cached payee: {result.payee} ({result.confidence} confidence){Style.RESET_ALL}"
                )
                return result
            # Otherwise, we'll try to improve it with Brave Search
            logger.info(
                f"{row_info} {Fore.YELLOW}⚠ Low confidence cache hit ({result.confidence}), will try to improve...{Style.RESET_ALL}"
            )

        # Get initial AI identification
        logger.info(f"{row_info} 🤖 Getting initial identification from LLM...")
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
            initial_response = PayeeResponse(**result)

            logger.info(
                f"{row_info} 🤖 LLM identified payee: {initial_response.payee} ({initial_response.confidence} confidence)"
            )

            if "business_description" in result:
                logger.info(
                    f"{row_info} 📋 Business type: {result['business_description']}"
                )

            if "general_category" in result:
                logger.info(
                    f"{row_info} 🏷️ General category: {result['general_category']}"
                )

            # If confidence is not high, try to enrich with Brave Search
            if initial_response.confidence != "high":
                logger.info(f"{row_info} 🔍 Enriching with Brave Search...")
                try:
                    # Look up vendor information
                    vendor_results = lookup_vendor_info(
                        initial_response.payee, max_results=3
                    )

                    if vendor_results:
                        # Get the most relevant result
                        best_match = vendor_results[0]

                        # If we got a good business match
                        if best_match["relevance_score"] >= 5:
                            logger.info(
                                f"{row_info} {Fore.GREEN}✓ Found business match: {best_match['title']} (score: {best_match['relevance_score']}){Style.RESET_ALL}"
                            )

                            # Update the payee name if we found a better one
                            if best_match["title"] != initial_response.payee:
                                initial_response.payee = best_match["title"]
                                logger.info(
                                    f"{row_info} {Fore.GREEN}✓ Updated payee name to: {initial_response.payee}{Style.RESET_ALL}"
                                )

                            # Upgrade confidence if we found a strong business match
                            if initial_response.confidence == "low":
                                initial_response.confidence = "medium"
                                logger.info(
                                    f"{row_info} {Fore.GREEN}✓ Upgraded confidence to medium{Style.RESET_ALL}"
                                )

                            # Add the business information to the reasoning
                            initial_response.reasoning += f"\n\nEnriched with business information: {best_match['description']}"

                            # If we don't have a business description yet, extract one from the search result
                            if (
                                not result.get("business_description")
                                or result.get("business_description") == "Unknown"
                            ):
                                # Try to extract a business description from the search result
                                prompt = f"""Based on this search result, provide a VERY brief (10 words or less) description of what type of business {initial_response.payee} is:

Search result: {best_match['description']}

ONLY return the brief business description, nothing else."""

                                description_response = self.client.responses.create(
                                    model="claude-3-haiku-20240307",
                                    input=[{"role": "user", "content": prompt}],
                                )

                                business_description = (
                                    description_response.output_text.strip()
                                )
                                result["business_description"] = business_description
                                logger.info(
                                    f"{row_info} {Fore.GREEN}✓ Added business description from search: {business_description}{Style.RESET_ALL}"
                                )
                        else:
                            logger.info(
                                f"{row_info} {Fore.YELLOW}⚠ No good business match found (best score: {best_match['relevance_score']}){Style.RESET_ALL}"
                            )

                except Exception as e:
                    logger.warning(
                        f"{row_info} {Fore.YELLOW}⚠ Brave Search error: {str(e)}{Style.RESET_ALL}"
                    )

            # Cache the result with all fields
            self._cache_result(
                cache_key,
                "payee",
                result,
            )

            logger.info(
                f"{row_info} {Fore.GREEN}✓ FINAL PAYEE: {initial_response.payee} ({initial_response.confidence} confidence){Style.RESET_ALL}"
            )

            return initial_response

        except Exception as e:
            logger.error(f"{row_info} {Fore.RED}❌ Error: {str(e)}{Style.RESET_ALL}")
            return PayeeResponse(
                payee="Unknown Payee",
                confidence="low",
                reasoning=f"Error: {str(e)}",
            )

    def _get_category(
        self,
        description: str,
        payee: str,
        business_description: str = None,
        general_category: str = None,
    ) -> CategoryResponse:
        """Process a single transaction to assign a base category.

        This assigns an initial business-friendly category, which will later be mapped to
        Schedule 6A categories in pass 3.

        Args:
            description: Transaction description
            payee: Identified payee name
            business_description: Optional description of the payee business
            general_category: Optional general expense category from Pass 1
        """
        # Get client's custom categories
        client_categories = self.db.get_client_categories(self.client_name)
        custom_categories = [cat["category_name"] for cat in client_categories]

        # Define base business categories (more intuitive than 6A categories)
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

        # Combine all categories
        available_categories = (
            base_business_categories + personal_categories + custom_categories
        )

        # Build context information about the transaction
        transaction_context = f"""Transaction Description: {description}
Payee: {payee}"""

        if business_description:
            transaction_context += f"\nBusiness Type: {business_description}"

        if general_category:
            transaction_context += f"\nGeneral Category from Pass 1: {general_category}"

        # Separate categories by type for the prompt
        business_categories_str = "\n".join(
            f"- {cat}" for cat in base_business_categories
        )
        personal_categories_str = "\n".join(f"- {cat}" for cat in personal_categories)
        custom_categories_str = (
            "\n".join(f"- {cat}" for cat in custom_categories)
            if custom_categories
            else "None"
        )

        prompt = f"""Analyze this transaction to determine if it's a business or personal expense, and assign the most appropriate category.

Transaction Information:
{transaction_context}

Business Context:
{self.business_context}

Business Categories:
{business_categories_str}

Personal Categories:
{personal_categories_str}

Client Custom Categories:
{custom_categories_str}

Please analyze this transaction and provide:
1. Whether this is primarily a business or personal expense
2. The most appropriate category from the lists above
3. A clear explanation of your reasoning, including how it relates to real estate operations if business-related
4. The percentage of business use (100% for purely business, 0% for purely personal, or a percentage for mixed use)

Response Format:
- category: The assigned expense category
- expense_type: "business", "personal", or "mixed"
- business_percentage: Percentage of business use (0-100)
- confidence: Your confidence level ("high", "medium", "low")
- reasoning: Your explanation, including how this relates to real estate operations if business-related
- business_context: Specific explanation of how this expense relates to the client's real estate business

Rules:
1. Focus on the nature of the expense, not just the payee
2. Consider the business context when categorizing
3. If it's a business expense, explain how it relates to real estate operations
4. If it's a personal expense, explain why it doesn't qualify as a business expense
5. For mixed expenses, estimate the business percentage and explain your reasoning
6. If a custom category fits better than the standard categories, use it
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
                    "name": "category_response",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "The assigned expense category",
                            },
                            "expense_type": {
                                "type": "string",
                                "enum": ["business", "personal", "mixed"],
                                "description": "Whether this is a business or personal expense",
                            },
                            "business_percentage": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "Percentage of business use (0-100)",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence level in the assignment",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation of why this category is appropriate",
                            },
                            "business_context": {
                                "type": "string",
                                "description": "Specific explanation of how this expense relates to real estate operations",
                            },
                        },
                        "required": [
                            "category",
                            "expense_type",
                            "business_percentage",
                            "confidence",
                            "reasoning",
                            "business_context",
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

            # Validate the category exists in our available categories
            if result["category"] not in available_categories:
                # Default to appropriate "Other" category based on expense_type
                if result["expense_type"] == "business":
                    result["category"] = "Other Business Expenses"
                else:
                    result["category"] = "Other Personal Expenses"

                result["confidence"] = "low"
                result[
                    "reasoning"
                ] += "\nCategory not found in available list, defaulting to appropriate 'Other' category."

            # Add expense_type to the CategoryResponse
            # Combine reasoning and business context
            full_reasoning = f"{result['reasoning']}\n\nExpense type: {result['expense_type']}\nBusiness percentage: {result['business_percentage']}%\n\nBusiness context: {result['business_context']}"

            return CategoryResponse(
                category=result["category"],
                confidence=result["confidence"],
                reasoning=full_reasoning,
            )
        except Exception as e:
            logger.error(f"Error parsing category response: {str(e)}")
            return CategoryResponse(
                category="Other Personal Expenses",
                confidence="low",
                reasoning=f"Error during processing: {str(e)}",
            )

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


@dataclass
class ClassificationResponse:
    """Response from classification step."""

    tax_category: str
    tax_subcategory: str = ""
    worksheet: str = "6A"
    confidence: str = "medium"
    reasoning: str = ""
