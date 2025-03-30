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

        # Use client's custom categories if available, otherwise use standard
        self.categories = (
            self.business_profile.get("custom_categories", [])
            + self.business_profile.get("ai_generated_categories", [])
            + STANDARD_CATEGORIES
        )

        # Get business context for AI prompts
        self.business_context = self._get_business_context()

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

    def classify_transactions(
        self,
        transactions_df: pd.DataFrame,
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
        resume_from_pass: Optional[int] = None,
    ) -> pd.DataFrame:
        """Classify transactions in the DataFrame using a three-pass approach.

        Args:
            transactions_df: DataFrame containing transactions to classify
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

        # Create output directory if it doesn't exist
        output_dir = os.path.join("data", "transactions", "output")
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
            print(f"Pass 1: Processing payees for rows {start_row}-{end_row}...")
            for idx in range(start_row, end_row):
                try:
                    payee_result = self._get_payee(
                        transactions_df.iloc[idx]["description"]
                    )
                    transactions_df.at[idx, "payee"] = payee_result.payee
                    transactions_df.at[idx, "payee_confidence"] = (
                        payee_result.confidence
                    )
                    transactions_df.at[idx, "payee_reasoning"] = payee_result.reasoning
                except Exception as e:
                    print(f"Error processing payee for transaction {idx}: {str(e)}")
                    transactions_df.at[idx, "payee"] = "Unknown Payee"
                    transactions_df.at[idx, "payee_confidence"] = "low"
                    transactions_df.at[idx, "payee_reasoning"] = (
                        f"Error during processing: {str(e)}"
                    )

            # Save results after payee pass
            payee_file = os.path.join(output_dir, f"{base_filename}_payee_pass.csv")
            transactions_df.to_csv(payee_file, index=False)
            print(f"Saved payee pass results to {payee_file}")

        # Pass 2: Process all categories
        if resume_from_pass is None or resume_from_pass <= 2:
            print(f"Pass 2: Processing categories for rows {start_row}-{end_row}...")
            for idx in range(start_row, end_row):
                try:
                    category_result = self._get_category(
                        transactions_df.iloc[idx]["description"],
                        transactions_df.iloc[idx]["payee"],
                    )
                    transactions_df.at[idx, "category"] = category_result.category
                    transactions_df.at[idx, "category_confidence"] = (
                        category_result.confidence
                    )
                    transactions_df.at[idx, "category_reasoning"] = (
                        category_result.reasoning
                    )
                    transactions_df.at[idx, "suggested_new_category"] = (
                        category_result.suggested_new_category
                    )
                    transactions_df.at[idx, "new_category_reasoning"] = (
                        category_result.new_category_reasoning
                    )
                except Exception as e:
                    print(f"Error processing category for transaction {idx}: {str(e)}")
                    transactions_df.at[idx, "category"] = "Unclassified"
                    transactions_df.at[idx, "category_confidence"] = "low"
                    transactions_df.at[idx, "category_reasoning"] = (
                        f"Error during processing: {str(e)}"
                    )

            # Save results after category pass
            category_file = os.path.join(
                output_dir, f"{base_filename}_category_pass.csv"
            )
            transactions_df.to_csv(category_file, index=False)
            print(f"Saved category pass results to {category_file}")

        # Pass 3: Process all classifications
        if resume_from_pass is None or resume_from_pass <= 3:
            print(
                f"Pass 3: Processing classifications for rows {start_row}-{end_row}..."
            )
            for idx in range(start_row, end_row):
                try:
                    classification_result = self._get_classification(
                        transactions_df.iloc[idx]["description"],
                        transactions_df.iloc[idx]["payee"],
                        transactions_df.iloc[idx]["category"],
                    )
                    transactions_df.at[idx, "classification"] = (
                        classification_result.classification
                    )
                    transactions_df.at[idx, "classification_confidence"] = (
                        classification_result.confidence
                    )
                    transactions_df.at[idx, "classification_reasoning"] = (
                        classification_result.reasoning
                    )
                    transactions_df.at[idx, "tax_implications"] = (
                        classification_result.tax_implications
                    )
                except Exception as e:
                    print(
                        f"Error processing classification for transaction {idx}: {str(e)}"
                    )
                    transactions_df.at[idx, "classification"] = "Unclassified"
                    transactions_df.at[idx, "classification_confidence"] = "low"
                    transactions_df.at[idx, "classification_reasoning"] = (
                        f"Error during processing: {str(e)}"
                    )

            # Save final results
            final_file = os.path.join(output_dir, f"{base_filename}_final.csv")
            transactions_df.to_csv(final_file, index=False)
            print(f"Saved final results to {final_file}")

        return transactions_df

    def _get_payee(self, description: str) -> PayeeResponse:
        """Identify the payee/merchant from the transaction description."""
        prompt = (
            PROMPTS["get_payee"]
            + f"\n\nTransaction: {description}\n\nBusiness Context:\n{self.business_context}"
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

        print(f"Raw response: {response.output_text}")  # Debug log
        try:
            # Clean up the response text to ensure valid JSON
            response_text = response.output_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            return PayeeResponse(**json.loads(response_text))
        except Exception as e:
            print(f"Error parsing response: {str(e)}")
            print(f"Response content: {response.output_text}")
            raise

    def _get_category(self, description: str, payee: str) -> CategoryResponse:
        """Categorize the transaction based on description and payee."""
        print("\nDEBUG: Entering _get_category method")
        print(f"DEBUG: Description: {description}")
        print(f"DEBUG: Payee: {payee}")

        # Use AI-generated categories from business profile
        categories = self.business_profile.get("ai_generated_categories", [])
        print(f"DEBUG: Using AI-generated categories: {categories}")

        print(f"\n=== Starting category processing for: {description} ===")

        # Format categories as a simple comma-separated list
        formatted_categories = ", ".join(categories)

        # Construct the prompt with proper formatting
        prompt = f"""Categorize the transaction based on the description and payee.

Available categories: {formatted_categories}

IMPORTANT: Return a JSON object with EXACTLY these field names:
{{
    "category": "string - The assigned category from the list",
    "confidence": "string - Must be exactly 'high', 'medium', or 'low'",
    "reasoning": "string - Explanation of the categorization",
    "suggested_new_category": "string or null - New category if needed",
    "new_category_reasoning": "string or null - Explanation for suggested new category"
}}

Example:
{{
    "category": "Content Production",
    "confidence": "high",
    "reasoning": "Purchase of video production equipment",
    "suggested_new_category": null,
    "new_category_reasoning": null
}}

Transaction: {description}
Payee: {payee}

Business Context:
{self.business_context}"""

        print(f"Prompt being sent: {prompt}")

        try:
            print("Making API call...")
            # Simplified payload
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
                                    "description": "The assigned category from the list",
                                },
                                "confidence": {
                                    "type": "string",
                                    "enum": ["high", "medium", "low"],
                                    "description": "Confidence level in the categorization",
                                },
                                "reasoning": {
                                    "type": "string",
                                    "description": "Explanation of the categorization",
                                },
                                "suggested_new_category": {
                                    "type": ["string", "null"],
                                    "description": "New category if needed",
                                },
                                "new_category_reasoning": {
                                    "type": ["string", "null"],
                                    "description": "Explanation for suggested new category",
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
            print("API call completed")
            print(f"Raw category response: {response.output_text}")  # Debug log

            # Clean up the response text to ensure valid JSON
            response_text = response.output_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            # Parse the response
            response_data = json.loads(response_text)

            # Handle null values for optional fields
            if "suggested_new_category" not in response_data:
                response_data["suggested_new_category"] = None
            if "new_category_reasoning" not in response_data:
                response_data["new_category_reasoning"] = None

            return CategoryResponse(**response_data)
        except Exception as e:
            print(f"Error in category processing: {str(e)}")
            print(f"Error type: {type(e)}")
            print(f"Error args: {e.args}")
            if "response" in locals():
                print(f"Response content: {response.output_text}")
            raise

    def _get_classification(
        self, description: str, payee: str, category: str
    ) -> ClassificationResponse:
        """Classify the transaction as business or personal."""
        prompt = (
            PROMPTS["get_classification"]
            + f"\n\nTransaction: {description}\nPayee: {payee}\nCategory: {category}\n\nBusiness Context:\n{self.business_context}"
        )

        response = self.client.responses.create(
            model=self._get_model(),
            input=[
                {
                    "role": "system",
                    "content": ASSISTANTS_CONFIG["DaveAI"]["instructions"],
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
                                "enum": ["Business", "Personal", "Unclassified"],
                                "description": "Classification result",
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
                                "type": ["string", "null"],
                                "description": "Tax implications if relevant",
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

        print(f"Raw classification response: {response.output_text}")  # Debug log
        try:
            # Clean up the response text to ensure valid JSON
            response_text = response.output_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            return ClassificationResponse(**json.loads(response_text))
        except Exception as e:
            print(f"Error parsing classification response: {str(e)}")
            print(f"Response content: {response.output_text}")
            raise

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
