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

                    # Update transaction with payee info
                    self.db.update_transaction_classification(
                        transaction["transaction_id"],
                        {
                            "client_id": self.db.get_client_id(self.client_name),
                            "payee": payee_info.payee,
                            "payee_confidence": payee_info.confidence,
                            "payee_reasoning": payee_info.reasoning,
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
                            transaction["description"], existing["payee"]
                        )
                        logger.info(
                            f"[Row {row_number}] ✓ Category assigned: {category_info.category} (confidence: {category_info.confidence})"
                        )

                    # Extract expense_type from reasoning
                    expense_type = "personal"  # Default to personal
                    if "Expense type: business" in category_info.reasoning:
                        expense_type = "business"
                    elif "Expense type: mixed" in category_info.reasoning:
                        expense_type = "mixed"

                    logger.info(f"[Row {row_number}] • Expense type: {expense_type}")

                    # Update transaction with category info
                    self.db.update_transaction_classification(
                        transaction["transaction_id"],
                        {
                            "client_id": self.db.get_client_id(self.client_name),
                            "base_category": category_info.category,
                            "category_confidence": category_info.confidence,
                            "category_reasoning": category_info.reasoning,
                            "expense_type": expense_type,
                        },
                    )

                    # Cache the result with expense_type
                    if not cached_category:
                        self._cache_result(
                            cache_key,
                            "category",
                            {
                                "category": category_info.category,
                                "confidence": category_info.confidence,
                                "reasoning": category_info.reasoning,
                                "expense_type": expense_type,
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
                        f"{Fore.GREEN}✓ Pass 2 complete: {category_info.category} ({expense_type}){Style.RESET_ALL}"
                    )
                    processed_count[2] += 1

                    # If we're only doing up to pass 2, continue to next transaction
                    if resume_from_pass == 2:
                        continue

                # Pass 3: Final classification
                if resume_from_pass <= 3:
                    logger.info(
                        f"{Fore.GREEN}▶ PASS 3: Final Classification & Tax Mapping{Style.RESET_ALL}"
                    )

                    # Get existing info
                    existing = self.db.get_transaction_classification(
                        transaction["transaction_id"]
                    )
                    if not existing or not existing.get("base_category"):
                        logger.warning(
                            f"[Row {row_number}] ⚠ No category found from pass 2, skipping pass 3"
                        )
                        continue

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
                            f"[Row {row_number}] ✓ Using cached classification: {cached_classification['classification']} (confidence: {cached_classification['confidence']})"
                        )
                        classification_info = ClassificationResponse(
                            **cached_classification
                        )
                        cache_hit_count[3] += 1

                        # If we have a tax_category in the cache, use it
                        tax_category = cached_classification.get(
                            "tax_category", "Other expenses"
                        )
                        business_percentage = cached_classification.get(
                            "business_percentage",
                            (
                                100
                                if cached_classification.get("classification")
                                == "Business"
                                else 0
                            ),
                        )

                        logger.info(
                            f"[Row {row_number}] • Tax category: {tax_category}"
                        )
                        logger.info(
                            f"[Row {row_number}] • Business percentage: {business_percentage}%"
                        )
                    else:
                        # Get classification info from LLM
                        logger.info(
                            f"[Row {row_number}] 🤖 Getting classification for {existing['base_category']}"
                        )
                        classification_info = self._get_classification(
                            transaction["description"],
                            existing["payee"],
                            existing["base_category"],
                        )
                        logger.info(
                            f"[Row {row_number}] ✓ Classification: {classification_info.classification} (confidence: {classification_info.confidence})"
                        )

                        # Extract tax_category and business_percentage from the response or database
                        # These might have been set in the _get_classification method
                        updated = self.db.get_transaction_classification(
                            transaction["transaction_id"]
                        )
                        tax_category = updated.get("tax_category", "Other expenses")
                        business_percentage = updated.get(
                            "business_percentage",
                            (
                                100
                                if classification_info.classification == "Business"
                                else 0
                            ),
                        )

                        logger.info(
                            f"[Row {row_number}] • Tax category: {tax_category}"
                        )
                        logger.info(
                            f"[Row {row_number}] • Business percentage: {business_percentage}%"
                        )

                        # Cache the result with tax_category
                        self._cache_result(
                            cache_key,
                            "classification",
                            {
                                "classification": classification_info.classification,
                                "confidence": classification_info.confidence,
                                "reasoning": classification_info.reasoning,
                                "tax_implications": classification_info.tax_implications,
                                "tax_category": tax_category,
                                "business_percentage": business_percentage,
                            },
                        )

                    # Update transaction with classification info
                    self.db.update_transaction_classification(
                        transaction["transaction_id"],
                        {
                            "client_id": self.db.get_client_id(self.client_name),
                            "classification": classification_info.classification,
                            "classification_confidence": classification_info.confidence,
                            "classification_reasoning": classification_info.reasoning,
                            "tax_implications": classification_info.tax_implications,
                            "tax_category": tax_category,
                            "business_percentage": business_percentage,
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
                        f"{Fore.GREEN}✓ Pass 3 complete: {classification_info.classification} → {tax_category}{Style.RESET_ALL}"
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
        prompt = (
            PROMPTS["get_payee"]
            + f"\n\nBusiness Context:\n{self.business_context}\n\n"
            + f"Process the following transaction:\n- {description}"
        )

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
                        "required": ["payee", "confidence", "reasoning"],
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
                        else:
                            logger.info(
                                f"{row_info} {Fore.YELLOW}⚠ No good business match found (best score: {best_match['relevance_score']}){Style.RESET_ALL}"
                            )

                except Exception as e:
                    logger.warning(
                        f"{row_info} {Fore.YELLOW}⚠ Brave Search error: {str(e)}{Style.RESET_ALL}"
                    )

            # Cache the result regardless of confidence
            # This way we know if we've tried Brave Search before
            self._cache_result(
                cache_key,
                "payee",
                {
                    "payee": initial_response.payee,
                    "confidence": initial_response.confidence,
                    "reasoning": initial_response.reasoning,
                },
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

    def _get_category(self, description: str, payee: str) -> CategoryResponse:
        """Process a single transaction to assign a base category.

        This assigns an initial business or personal category, which will later be mapped to
        Schedule 6A categories in pass 3 if applicable.
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
            "Charity and Gifts",
            "Personal Insurance",
            "Personal Finance",
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

        prompt = f"""Analyze this transaction and assign it to the most appropriate category (business or personal).

Business Categories:
{business_categories_str}

Personal Categories:
{personal_categories_str}

Client Custom Categories:
{custom_categories_str}

Business Context:
{self.business_context}

Transaction:
Description: {description}
Payee: {payee}

Rules:
1. Choose from the available categories listed above
2. If it's a business expense, select from the business categories section
3. If it's a personal expense, select from the personal categories section
4. If a custom category fits better than the standard categories, use it
5. Focus on the nature of the expense, not just the payee
6. Consider the business context when categorizing
7. If completely unsure, use "Other Personal Expenses" or "Other Business Expenses" as appropriate
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
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence level in the assignment",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation of why this category is appropriate",
                            },
                        },
                        "required": [
                            "category",
                            "expense_type",
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

            # Add expense_type to the CategoryResponse (even though it's not in the model)
            # The DB will be updated to include this field in pass 3
            return CategoryResponse(
                category=result["category"],
                confidence=result["confidence"],
                reasoning=f"{result['reasoning']}\n\nExpense type: {result['expense_type']}",
            )
        except Exception as e:
            logger.error(f"Error parsing category response: {str(e)}")
            return CategoryResponse(
                category="Other Personal Expenses",
                confidence="low",
                reasoning=f"Error during processing: {str(e)}",
            )

    def _get_classification(
        self, description: str, payee: str, category: str
    ) -> ClassificationResponse:
        """Process a transaction to determine classification and, for business expenses, map to Schedule 6A."""
        # Get transaction details from the database
        transaction_id = None
        expense_type = None

        # Try to find the transaction in the database using description and payee
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT tc.transaction_id, tc.expense_type 
                FROM transaction_classifications tc
                JOIN transactions t ON tc.transaction_id = t.transaction_id
                WHERE t.description = ? AND tc.payee = ?
                AND tc.client_id = ?
                LIMIT 1
                """,
                (description, payee, self.db.get_client_id(self.client_name)),
            )
            result = cursor.fetchone()
            if result:
                transaction_id, expense_type = result

        # Get IRS Schedule 6A categories
        schedule_6a_categories = list(
            TAX_WORKSHEET_CATEGORIES["6A"]["main_expenses"].keys()
        )
        schedule_6a_mapping = "\n".join(
            [
                f"- {cat}: {TAX_WORKSHEET_CATEGORIES['6A']['main_expenses'][cat]['description']}"
                for cat in schedule_6a_categories
            ]
        )

        # Customize prompt based on expense type
        if expense_type == "business" or expense_type == "mixed":
            prompt = f"""Analyze this transaction to finalize its classification and map business expenses to the appropriate IRS Schedule 6A category.

Transaction:
- Description: {description}
- Payee: {payee}
- Initial Category: {category}
- Initial Expense Type: {expense_type}

Business Context:
{self.business_context}

First, confirm the classification as:
- Business: Fully deductible business expense
- Personal: Non-deductible personal expense
- Mixed: Partially business, partially personal

For business or mixed expenses, map to one of these IRS Schedule 6A categories:
{schedule_6a_mapping}

Rules:
1. Confirm expense_type based on transaction details and business context
2. For business expenses, select the most appropriate Schedule 6A category
3. For mixed expenses, indicate business percentage if possible
4. For personal expenses, keep the original category
5. Provide tax implications appropriate for the classification
"""
        else:  # Personal expense
            prompt = f"""Analyze this transaction to finalize its classification.

Transaction:
- Description: {description}
- Payee: {payee}
- Initial Category: {category}
- Initial Expense Type: personal

Business Context:
{self.business_context}

Confirm the classification as:
- Business: Fully deductible business expense
- Personal: Non-deductible personal expense
- Mixed: Partially business, partially personal

Rules:
1. Verify this is truly a personal expense based on transaction details
2. If it's actually business-related, explain why
3. If personal, keep the original category and explain why it's not business-related
4. Provide tax implications appropriate for the classification
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
                    "name": "classification_response",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "classification": {
                                "type": "string",
                                "enum": [
                                    "Business",
                                    "Personal",
                                    "Mixed",
                                    "Unclassified",
                                ],
                                "description": "The transaction classification (must be one of: Business, Personal, Mixed, or Unclassified)",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence level in the classification",
                            },
                            "tax_category": {
                                "type": "string",
                                "description": "For business expenses, the IRS Schedule 6A category; for personal expenses, the original category",
                            },
                            "business_percentage": {
                                "type": "integer",
                                "minimum": 0,
                                "maximum": 100,
                                "description": "For mixed expenses, percentage that is business (0-100)",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation of the classification",
                            },
                            "tax_implications": {
                                "type": "string",
                                "description": "Tax implications of the classification",
                            },
                        },
                        "required": [
                            "classification",
                            "confidence",
                            "tax_category",
                            "reasoning",
                            "tax_implications",
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

            # Ensure classification is properly capitalized
            result["classification"] = result["classification"].capitalize()
            if result["classification"] not in ["Business", "Personal", "Mixed"]:
                result["classification"] = "Unclassified"

            # Validate tax_category for business expenses
            if (
                result["classification"] == "Business"
                and result["tax_category"] not in schedule_6a_categories
            ):
                # Try to find the closest match
                result["tax_category"] = "Other expenses"
                result["confidence"] = "low"
                result[
                    "reasoning"
                ] += "\nProvided tax category not found in Schedule 6A, defaulting to 'Other expenses'."

            # For personal expenses, we don't need to validate against Schedule 6A

            # Update the database with the final tax category if we have a transaction_id
            if transaction_id and result["classification"] in ["Business", "Mixed"]:
                self.db.update_transaction_classification(
                    transaction_id,
                    {
                        "tax_category": result["tax_category"],
                        "business_percentage": result.get(
                            "business_percentage",
                            100 if result["classification"] == "Business" else 0,
                        ),
                    },
                )

            # Construct the final response
            return ClassificationResponse(
                classification=result["classification"],
                confidence=result["confidence"],
                reasoning=result["reasoning"],
                tax_implications=result["tax_implications"],
            )
        except Exception as e:
            logger.error(f"Error parsing classification response: {str(e)}")
            return ClassificationResponse(
                classification="Unclassified",
                confidence="low",
                reasoning=f"Error: {str(e)}",
                tax_implications="Error during processing",
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
