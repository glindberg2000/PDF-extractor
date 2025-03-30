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

    def classify_transactions(self, transactions_df: pd.DataFrame) -> pd.DataFrame:
        """Classify all transactions in the DataFrame using a three-pass approach.

        Args:
            transactions_df: DataFrame containing transactions to classify

        Returns:
            DataFrame with added classification columns
        """
        # Initialize new columns
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
        print("Pass 1: Processing payees...")
        for idx, row in transactions_df.iterrows():
            try:
                payee_result = self._get_payee(row["description"])
                transactions_df.at[idx, "payee"] = payee_result.payee
                transactions_df.at[idx, "payee_confidence"] = payee_result.confidence
                transactions_df.at[idx, "payee_reasoning"] = payee_result.reasoning
            except Exception as e:
                print(f"Error processing payee for transaction {idx}: {str(e)}")
                transactions_df.at[idx, "payee"] = "Unknown Payee"
                transactions_df.at[idx, "payee_confidence"] = "low"
                transactions_df.at[idx, "payee_reasoning"] = (
                    f"Error during processing: {str(e)}"
                )

        # Pass 2: Process all categories
        print("Pass 2: Processing categories...")
        for idx, row in transactions_df.iterrows():
            try:
                category_result = self._get_category(row["description"], row["payee"])
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

        # Pass 3: Process all classifications
        print("Pass 3: Processing classifications...")
        for idx, row in transactions_df.iterrows():
            try:
                classification_result = self._get_classification(
                    row["description"], row["payee"], row["category"]
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
        formatted_categories = ", ".join([f'"{cat}"' for cat in self.categories])
        prompt = (
            PROMPTS["get_category"].format(categories=formatted_categories)
            + f"\n\nTransaction: {description}\nPayee: {payee}\n\nBusiness Context:\n{self.business_context}"
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

        print(f"Raw category response: {response.output_text}")  # Debug log
        try:
            # Clean up the response text to ensure valid JSON
            response_text = response.output_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()

            return CategoryResponse(**json.loads(response_text))
        except Exception as e:
            print(f"Error parsing category response: {str(e)}")
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
