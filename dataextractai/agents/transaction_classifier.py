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

logger = logging.getLogger(__name__)


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
                print(
                    f"\n[CACHE HIT] Found cached {pass_type} result for transaction: {cache_key}"
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
    ) -> None:
        """Process transactions through multiple passes.

        Pass 1: Identify payees and basic transaction info
        Pass 2: Determine base category and initial classification
        Pass 3: Assign tax worksheet, category, and handle splits

        Args:
            transactions: DataFrame of transactions to process
            resume_from_pass: Which pass to start from (1-3)
            force_process: Whether to reprocess already processed transactions
            batch_size: Number of transactions to process at once
        """
        if not isinstance(transactions, pd.DataFrame):
            raise ValueError("transactions must be a pandas DataFrame")

        if resume_from_pass < 1 or resume_from_pass > 3:
            raise ValueError("resume_from_pass must be between 1 and 3")

        total_transactions = len(transactions)
        logger.info(
            f"Processing {total_transactions} transactions starting from pass {resume_from_pass}"
        )

        # Pass 1: Identify payees
        if resume_from_pass == 1:
            logger.info("Starting Pass 1: Payee Identification")
            for i in range(0, total_transactions, batch_size):
                batch = transactions.iloc[i : i + batch_size]
                for _, transaction in batch.iterrows():
                    if not force_process:
                        # Check if already processed
                        status = self.db.get_transaction_status(
                            transaction["transaction_id"]
                        )
                        if status and status["pass_1_complete"]:
                            continue

                    try:
                        # Get payee info
                        payee_info = self._get_payee(transaction)

                        # Update transaction classifications
                        self.db.update_transaction_classification(
                            transaction["transaction_id"],
                            {
                                "payee": payee_info["payee"],
                                "payee_confidence": payee_info["confidence"],
                            },
                        )

                        # Update status
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "pass_1_complete": True,
                                "pass_1_error": None,
                                "pass_1_completed_at": datetime.now(),
                            },
                        )
                    except Exception as e:
                        logger.error(
                            f"Error in Pass 1 for transaction {transaction['transaction_id']}: {str(e)}"
                        )
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "pass_1_complete": False,
                                "pass_1_error": str(e),
                                "pass_1_completed_at": datetime.now(),
                            },
                        )

        # Pass 2: Base category assignment
        if resume_from_pass <= 2:
            logger.info("Starting Pass 2: Base Category Assignment")
            for i in range(0, total_transactions, batch_size):
                batch = transactions.iloc[i : i + batch_size]
                for _, transaction in batch.iterrows():
                    if not force_process:
                        # Check if already processed and has valid payee
                        status = self.db.get_transaction_status(
                            transaction["transaction_id"]
                        )
                        if not status or not status["pass_1_complete"]:
                            continue
                        if status["pass_2_complete"]:
                            continue

                    try:
                        # Get base category
                        category_info = self._get_base_category(transaction)

                        # Update transaction classifications
                        self.db.update_transaction_classification(
                            transaction["transaction_id"],
                            {
                                "base_category": category_info["category"],
                                "base_category_confidence": category_info["confidence"],
                            },
                        )

                        # Update status
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "pass_2_complete": True,
                                "pass_2_error": None,
                                "pass_2_completed_at": datetime.now(),
                            },
                        )
                    except Exception as e:
                        logger.error(
                            f"Error in Pass 2 for transaction {transaction['transaction_id']}: {str(e)}"
                        )
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "pass_2_complete": False,
                                "pass_2_error": str(e),
                                "pass_2_completed_at": datetime.now(),
                            },
                        )

        # Pass 3: Worksheet assignment and tax categorization
        if resume_from_pass <= 3:
            logger.info("Starting Pass 3: Worksheet Assignment")
            for i in range(0, total_transactions, batch_size):
                batch = transactions.iloc[i : i + batch_size]
                for _, transaction in batch.iterrows():
                    if not force_process:
                        # Check if already processed and has valid category
                        status = self.db.get_transaction_status(
                            transaction["transaction_id"]
                        )
                        if not status or not status["pass_2_complete"]:
                            continue
                        if status["pass_3_complete"]:
                            continue

                    try:
                        # Get existing classification
                        classification = self.db.get_transaction_classification(
                            transaction["transaction_id"]
                        )
                        if not classification or not classification["base_category"]:
                            raise ValueError("No base category found for transaction")

                        # Determine worksheet and tax category
                        worksheet_info = self._determine_worksheet(
                            transaction, classification["base_category"]
                        )

                        # Update transaction classifications
                        update_data = {
                            "worksheet": worksheet_info.worksheet,
                            "tax_category": worksheet_info.tax_category,
                            "tax_subcategory": worksheet_info.tax_subcategory,
                            "tax_worksheet_line_number": worksheet_info.line_number,
                            "needs_splitting": worksheet_info.needs_splitting,
                        }

                        if (
                            worksheet_info.needs_splitting
                            and worksheet_info.split_details
                        ):
                            # Handle split transactions here
                            # This would involve creating new split transactions
                            # and linking them to the original
                            pass

                        self.db.update_transaction_classification(
                            transaction["transaction_id"], update_data
                        )

                        # Update status
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "pass_3_complete": True,
                                "pass_3_error": None,
                                "pass_3_completed_at": datetime.now(),
                            },
                        )
                    except Exception as e:
                        logger.error(
                            f"Error in Pass 3 for transaction {transaction['transaction_id']}: {str(e)}"
                        )
                        self.db.update_transaction_status(
                            transaction["transaction_id"],
                            {
                                "pass_3_complete": False,
                                "pass_3_error": str(e),
                                "pass_3_completed_at": datetime.now(),
                            },
                        )

        logger.info("Transaction processing complete")

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

    def _get_payee(self, description: str) -> PayeeResponse:
        """Process a single description to identify payee."""
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
                print("Using cached payee result")
                return result
            # Otherwise, we'll try to improve it with Brave Search

        # Get initial AI identification
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

            # If confidence is not high, try to enrich with Brave Search
            if initial_response.confidence != "high":
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
                            # Update the payee name if we found a better one
                            if best_match["title"] != initial_response.payee:
                                initial_response.payee = best_match["title"]

                            # Upgrade confidence if we found a strong business match
                            if initial_response.confidence == "low":
                                initial_response.confidence = "medium"

                            # Add the business information to the reasoning
                            initial_response.reasoning += f"\n\nEnriched with business information: {best_match['description']}"

                            # Log the enrichment
                            logger.info(
                                f"Enriched payee information for '{initial_response.payee}' using Brave Search"
                            )

                except Exception as e:
                    # Log the error but don't fail the classification
                    logger.warning(f"Error enriching payee with Brave Search: {str(e)}")

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

            return initial_response

        except Exception as e:
            print(f"Error parsing payee response: {str(e)}")
            return PayeeResponse(
                payee="Unknown Payee",
                confidence="low",
                reasoning=f"Error: {str(e)}",
            )

    def _get_category(self, description: str, payee: str) -> CategoryResponse:
        """Process a single transaction to assign category."""
        prompt = (
            PROMPTS["get_category"]
            + f"\n\nBusiness Context:\n{self.business_context}\n\n"
            + f"Process the following transaction:\n- {description} (Payee: {payee})"
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
                    "name": "category_response",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "description": "The assigned category",
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["high", "medium", "low"],
                                "description": "Confidence level in the assignment",
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Explanation of the assignment",
                            },
                            "suggested_new_category": {
                                "type": "string",
                                "description": "Suggested new category if needed",
                            },
                            "new_category_reasoning": {
                                "type": "string",
                                "description": "Explanation for the new category",
                            },
                        },
                        "required": [
                            "category",
                            "confidence",
                            "reasoning",
                            "suggested_new_category",
                            "new_category_reasoning",
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
            return CategoryResponse(**result)
        except Exception as e:
            print(f"Error parsing category response: {str(e)}")
            return CategoryResponse(
                category="Unclassified",
                confidence="low",
                reasoning=f"Error: {str(e)}",
                suggested_new_category=None,
                new_category_reasoning=None,
            )

    def _get_classification(
        self, description: str, payee: str, category: str
    ) -> ClassificationResponse:
        """Process a single transaction to determine classification."""
        prompt = (
            PROMPTS["get_classification"]
            + f"\n\nBusiness Context:\n{self.business_context}\n\n"
            + f"Process the following transaction:\n- {description} (Payee: {payee}, Category: {category})"
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

            return ClassificationResponse(**result)
        except Exception as e:
            print(f"Error parsing classification response: {str(e)}")
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
