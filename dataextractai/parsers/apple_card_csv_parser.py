import os
import pandas as pd
from datetime import datetime
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)
import math
import numpy as np


def _replace_nan_with_none(obj):
    """Recursively replace NaN/np.nan/float('nan') with None in dicts/lists/values."""
    if isinstance(obj, float) and (
        math.isnan(obj) or (np is not None and obj == np.nan)
    ):
        return None
    if isinstance(obj, dict):
        return {k: _replace_nan_with_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan_with_none(v) for v in obj]
    return obj


class AppleCardCSVParser(BaseParser):
    """
    Parser for Apple Card CSV exports.
    """

    name = "apple_card_csv"
    description = "Parser for Apple Card CSV exports."
    file_types = [".csv"]

    @staticmethod
    def parse_amount(amount_str):
        try:
            if isinstance(amount_str, (int, float)):
                return float(amount_str)
            return float(str(amount_str).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
        except Exception:
            return None

    def parse_file(
        self, input_path: str, config: dict = None, original_filename: str = None
    ) -> ParserOutput:
        df = pd.read_csv(input_path)
        df.columns = [c.strip() for c in df.columns]

        # Normalize dates
        df["transaction_date"] = pd.to_datetime(
            df["Transaction Date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
        df["posted_date"] = pd.to_datetime(
            df["Clearing Date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")

        # Use the 'Type' column to determine transaction type
        df["transaction_type"] = df["Type"].apply(
            lambda x: "credit" if "payment" in str(x).lower() else "debit"
        )

        # Normalize amounts
        df["amount"] = df.apply(
            lambda row: self._normalize_amount(
                amount=row["Amount (USD)"],
                transaction_type=row["transaction_type"],
                is_charge_positive=True,  # In Apple Card CSVs, charges are positive
            ),
            axis=1,
        )

        df = df.rename(columns={"Description": "description"})

        transactions = [
            TransactionRecord(**_replace_nan_with_none(row))
            for row in df.to_dict(orient="records")
        ]

        metadata = StatementMetadata(
            statement_date=transactions[-1].transaction_date if transactions else None,
            original_filename=os.path.basename(input_path),
            bank_name="Apple Card",
            account_type="Credit Card",
            parser_name=self.name,
        )

        return ParserOutput(
            transactions=transactions,
            metadata=metadata,
        )

    def normalize_data(self, raw_data: list[dict]) -> pd.DataFrame:
        normalized = []
        for row in raw_data:
            norm = {
                "transaction_date": row.get("transaction_date"),
                "post_date": row.get("post_date"),
                "amount": row.get("amount"),
                "description": row.get("description"),
                "merchant": row.get("merchant"),
                "category": row.get("category"),
                "type": row.get("type"),
                "purchased_by": row.get("purchased_by"),
                "source_file": row.get("source_file", ""),
                "file_path": row.get("file_path", ""),
                "file_name": row.get("file_name", ""),
                "source": row.get("source", self.name),
            }
            normalized.append(norm)
        return pd.DataFrame(normalized)

    @classmethod
    def can_parse(cls, file_path: str, **kwargs) -> bool:
        try:
            df = pd.read_csv(file_path, nrows=0)
            headers = set([str(h).strip() for h in df.columns])
            required_headers = {
                "Transaction Date",
                "Clearing Date",
                "Description",
                "Amount (USD)",
            }
            return required_headers.issubset(headers)
        except Exception:
            return False


ParserRegistry.register_parser(AppleCardCSVParser.name, AppleCardCSVParser)


def main(input_path: str) -> ParserOutput:
    """
    Canonical entrypoint for contract-based integration. Parses a single Apple Card CSV and returns a ParserOutput.
    Accepts a single file path and returns a ParserOutput object. No directory or batch logic.
    """
    parser = AppleCardCSVParser()
    return parser.parse_file(input_path)
