"""Transaction classifier for categorizing transactions using AI."""

import os
import json
import pandas as pd
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
import logging
from datetime import datetime
import re

from .client_profile_manager import ClientProfileManager

load_dotenv()

logger = logging.getLogger(__name__)

# Get model configurations from environment
OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18")
OPENAI_MODEL_PRECISE = os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31")


class TransactionClassifier:
    """Classifies transactions using AI and client business context."""

    def __init__(self, client_name: str):
        self.client_name = client_name
        self.client_dir = os.path.join("data", "clients", client_name)
        self.output_dir = os.path.join(self.client_dir, "output")
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.profile_manager = ClientProfileManager(client_name)

    def classify_transactions(self, transactions_df: pd.DataFrame) -> pd.DataFrame:
        """Classify transactions using AI and client business context."""
        if transactions_df.empty:
            logger.warning("No transactions to classify")
            return transactions_df

        # Add classification columns if they don't exist
        classification_columns = [
            "main_category",
            "subcategory",
            "confidence",
            "reasoning",
            "business_context",
            "questions",
        ]
        for col in classification_columns:
            if col not in transactions_df.columns:
                transactions_df[col] = None

        # Get the categorization prompt
        prompt_template = self.profile_manager.generate_categorization_prompt()
        if not prompt_template:
            logger.error("Failed to generate categorization prompt")
            return transactions_df

        # Process each transaction
        for idx, row in transactions_df.iterrows():
            # Skip transactions that don't need classification
            if self._should_skip_transaction(row):
                continue

            # Format the prompt with transaction details
            prompt = prompt_template.format(
                description=row["normalized_description"],
                amount=row["amount"],
                date=row["transaction_date"],
            )

            try:
                # Get AI classification
                response = self.client.chat.completions.create(
                    model=OPENAI_MODEL_PRECISE,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a transaction categorization expert.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                )

                classification = json.loads(response.choices[0].message.content)

                # Update the DataFrame with classification results
                for col in classification_columns:
                    transactions_df.at[idx, col] = classification.get(col)

                logger.info(
                    f"Classified transaction {idx}: {classification['main_category']} ({classification['confidence']})"
                )

            except Exception as e:
                logger.error(f"Error classifying transaction {idx}: {e}")

        # Save classified transactions
        output_file = os.path.join(
            self.output_dir, f"{self.client_name}_classified_transactions.csv"
        )
        transactions_df.to_csv(output_file, index=False)
        logger.info(f"Saved classified transactions to {output_file}")

        return transactions_df

    def _should_skip_transaction(self, transaction: pd.Series) -> bool:
        """Determine if a transaction should be skipped for classification."""
        # Skip transactions with no description
        if (
            pd.isna(transaction["normalized_description"])
            or not transaction["normalized_description"].strip()
        ):
            return True

        # Skip common transaction types that don't need classification
        skip_patterns = [
            r"ACH\s+CREDIT",  # ACH credits
            r"POS\s+CREDIT",  # POS credits
            r"DEPOSIT",  # Deposits
            r"INTEREST\s+CREDIT",  # Interest credits
            r"TRANSFER",  # Transfers
            r"ATM\s+WITHDRAWAL",  # ATM withdrawals
            r"FEE",  # Fees
            r"PAYMENT",  # Payments
            r"REFUND",  # Refunds
        ]

        description = transaction["normalized_description"].upper()
        return any(re.search(pattern, description) for pattern in skip_patterns)
