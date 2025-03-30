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

        # Initialize cache
        self.cache_file = os.path.join(
            "data", "clients", client_name, "output", "transaction_cache.json"
        )
        self.cache = self._load_cache()

        # Use client's custom categories if available, otherwise use standard
        self.categories = (
            self.business_profile.get("custom_categories", [])
            + self.business_profile.get("ai_generated_categories", [])
            + STANDARD_CATEGORIES
        )

        # Get business context for AI prompts
        self.business_context = self._get_business_context()

    def _load_cache(self) -> Dict:
        """Load the transaction cache from file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading cache: {str(e)}")
                return {}
        return {}

    def _save_cache(self) -> None:
        """Save the transaction cache to file."""
        try:
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"Error saving cache: {str(e)}")

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
        """Get a cached result for a transaction pass."""
        if cache_key in self.cache and pass_type in self.cache[cache_key]:
            print(
                f"\n[CACHE HIT] Found cached {pass_type} result for transaction: {cache_key}"
            )
            return self.cache[cache_key][pass_type]
        return None

    def _cache_result(self, cache_key: str, pass_type: str, result: Dict) -> None:
        """Cache a result for a transaction pass."""
        if cache_key not in self.cache:
            self.cache[cache_key] = {}
        self.cache[cache_key][pass_type] = result
        print(
            f"\n[CACHE MISS] Caching new {pass_type} result for transaction: {cache_key}"
        )
        self._save_cache()

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

    def process_transactions(
        self,
        transactions_df: pd.DataFrame,
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
        resume_from_pass: Optional[int] = None,
    ) -> pd.DataFrame:
        """Process transactions one at a time through three passes:
        1. Payee identification
        2. Category assignment
        3. Classification

        Args:
            transactions_df: DataFrame containing transactions
            start_row: Optional starting row index (inclusive)
            end_row: Optional ending row index (exclusive)
            resume_from_pass: Optional pass number to resume from (1=payee, 2=category, 3=classification)

        Returns:
            DataFrame with added classification columns
        """
        # Determine row range
        if start_row is None:
            start_row = 0
        if end_row is None:
            end_row = len(transactions_df)

        # Create output directory in client's folder
        output_dir = os.path.join("data", "clients", self.client_name, "output")
        os.makedirs(output_dir, exist_ok=True)

        # Generate output filename with row range
        range_suffix = (
            f"_{start_row}-{end_row}"
            if start_row != 0 or end_row != len(transactions_df)
            else ""
        )
        base_filename = f"{self.client_name}_classified_transactions{range_suffix}"

        # Initialize new columns if starting from beginning
        if resume_from_pass is None or resume_from_pass == 1:
            transactions_df["payee"] = None
            transactions_df["payee_confidence"] = None
            transactions_df["payee_reasoning"] = None
            transactions_df["category"] = None
            transactions_df["category_confidence"] = None
            transactions_df["category_reasoning"] = None
            transactions_df["suggested_new_category"] = None
            transactions_df["new_category_reasoning"] = None
            transactions_df["classification"] = None
            transactions_df["classification_confidence"] = None
            transactions_df["classification_reasoning"] = None
            transactions_df["tax_implications"] = None

        # Pass 1: Process all payees
        if resume_from_pass is None or resume_from_pass == 1:
            print(f"\nPass 1: Processing payees for rows {start_row}-{end_row}...")
            for row_idx in range(start_row, end_row):
                print(f"\nProcessing transaction {row_idx + 1}/{end_row}...")
                description = transactions_df.iloc[row_idx]["description"]
                cache_key = self._get_cache_key(description)

                try:
                    # Check cache first
                    cached_result = self._get_cached_result(cache_key, "payee")
                    if cached_result:
                        print("Using cached payee result")
                        result = PayeeResponse(**cached_result)
                    else:
                        result = self._get_payee(description)
                        # Cache the result
                        self._cache_result(
                            cache_key,
                            "payee",
                            {
                                "payee": result.payee,
                                "confidence": result.confidence,
                                "reasoning": result.reasoning,
                            },
                        )

                    transactions_df.at[row_idx, "payee"] = result.payee
                    transactions_df.at[row_idx, "payee_confidence"] = result.confidence
                    transactions_df.at[row_idx, "payee_reasoning"] = result.reasoning
                except Exception as e:
                    print(f"Error processing payee for transaction {row_idx}: {str(e)}")
                    transactions_df.at[row_idx, "payee"] = "Unknown Payee"
                    transactions_df.at[row_idx, "payee_confidence"] = "low"
                    transactions_df.at[row_idx, "payee_reasoning"] = (
                        f"Error during processing: {str(e)}"
                    )

            # Save results after payee pass
            payee_file = os.path.join(output_dir, f"{base_filename}_payee_pass.csv")
            transactions_df.to_csv(payee_file, index=False)
            print(f"\nSaved payee pass results to {payee_file}")

        # Pass 2: Process all categories
        if resume_from_pass is None or resume_from_pass <= 2:
            print(f"\nPass 2: Processing categories for rows {start_row}-{end_row}...")
            for row_idx in range(start_row, end_row):
                print(f"\nProcessing transaction {row_idx + 1}/{end_row}...")
                description = transactions_df.iloc[row_idx]["description"]
                payee = transactions_df.iloc[row_idx]["payee"]
                cache_key = self._get_cache_key(description, payee)

                try:
                    # Check cache first
                    cached_result = self._get_cached_result(cache_key, "category")
                    if cached_result:
                        print("Using cached category result")
                        result = CategoryResponse(**cached_result)
                    else:
                        result = self._get_category(description, payee)
                        # Cache the result
                        self._cache_result(
                            cache_key,
                            "category",
                            {
                                "category": result.category,
                                "confidence": result.confidence,
                                "reasoning": result.reasoning,
                                "suggested_new_category": result.suggested_new_category,
                                "new_category_reasoning": result.new_category_reasoning,
                            },
                        )

                    transactions_df.at[row_idx, "category"] = result.category
                    transactions_df.at[row_idx, "category_confidence"] = (
                        result.confidence
                    )
                    transactions_df.at[row_idx, "category_reasoning"] = result.reasoning
                    transactions_df.at[row_idx, "suggested_new_category"] = (
                        result.suggested_new_category
                    )
                    transactions_df.at[row_idx, "new_category_reasoning"] = (
                        result.new_category_reasoning
                    )
                except Exception as e:
                    print(
                        f"Error processing category for transaction {row_idx}: {str(e)}"
                    )
                    transactions_df.at[row_idx, "category"] = "Unclassified"
                    transactions_df.at[row_idx, "category_confidence"] = "low"
                    transactions_df.at[row_idx, "category_reasoning"] = (
                        f"Error during processing: {str(e)}"
                    )

            # Save results after category pass
            category_file = os.path.join(
                output_dir, f"{base_filename}_category_pass.csv"
            )
            transactions_df.to_csv(category_file, index=False)
            print(f"\nSaved category pass results to {category_file}")

        # Pass 3: Process all classifications
        if resume_from_pass is None or resume_from_pass <= 3:
            print(
                f"\nPass 3: Processing classifications for rows {start_row}-{end_row}..."
            )
            for row_idx in range(start_row, end_row):
                print(f"\nProcessing transaction {row_idx + 1}/{end_row}...")
                description = transactions_df.iloc[row_idx]["description"]
                payee = transactions_df.iloc[row_idx]["payee"]
                category = transactions_df.iloc[row_idx]["category"]
                cache_key = self._get_cache_key(description, payee, category)

                try:
                    # Check cache first
                    cached_result = self._get_cached_result(cache_key, "classification")
                    if cached_result:
                        print("Using cached classification result")
                        result = ClassificationResponse(**cached_result)
                    else:
                        result = self._get_classification(description, payee, category)
                        # Cache the result
                        self._cache_result(
                            cache_key,
                            "classification",
                            {
                                "classification": result.classification,
                                "confidence": result.confidence,
                                "reasoning": result.reasoning,
                                "tax_implications": result.tax_implications,
                            },
                        )

                    # Ensure classification is properly capitalized
                    classification = result.classification.capitalize()
                    if classification not in ["Business", "Personal", "Mixed"]:
                        classification = "Unclassified"

                    transactions_df.at[row_idx, "classification"] = classification
                    transactions_df.at[row_idx, "classification_confidence"] = (
                        result.confidence
                    )
                    transactions_df.at[row_idx, "classification_reasoning"] = (
                        result.reasoning
                    )
                    transactions_df.at[row_idx, "tax_implications"] = (
                        result.tax_implications
                    )
                except Exception as e:
                    print(
                        f"Error processing classification for transaction {row_idx}: {str(e)}"
                    )
                    transactions_df.at[row_idx, "classification"] = "Unclassified"
                    transactions_df.at[row_idx, "classification_confidence"] = "low"
                    transactions_df.at[row_idx, "classification_reasoning"] = (
                        f"Error during processing: {str(e)}"
                    )

            # Save final results
            final_file = os.path.join(output_dir, f"{base_filename}_final.csv")
            transactions_df.to_csv(final_file, index=False)
            print(f"\nSaved final results to {final_file}")

        return transactions_df

    def _get_payee(self, description: str) -> PayeeResponse:
        """Process a single description to identify payee."""
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
            return PayeeResponse(**result)
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
