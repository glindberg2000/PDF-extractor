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
    ) -> list[dict]:
        df = pd.read_csv(input_path)
        df["transaction_date"] = df["Transaction Date"].apply(self.parse_date)
        df["post_date"] = df["Clearing Date"].apply(self.parse_date)
        df["amount"] = df["Amount (USD)"].apply(self.parse_amount)
        df["description"] = df["Description"].fillna("")
        records = []
        for _, row in df.iterrows():
            records.append(
                {
                    "transaction_date": row["transaction_date"],
                    "post_date": row["post_date"],
                    "amount": row["amount"],
                    "description": row["description"],
                    "merchant": row.get("Merchant", None),
                    "category": row.get("Category", None),
                    "type": row.get("Type", None),
                    "purchased_by": row.get("Purchased By", None),
                    "source_file": os.path.basename(input_path),
                    "file_path": input_path,
                    "file_name": os.path.basename(input_path),
                    "source": self.name,
                }
            )
        return records

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
                "Amount (USD)",
                "Description",
            }
            return required_headers.issubset(headers)
        except Exception:
            return False


ParserRegistry.register_parser(AppleCardCSVParser.name, AppleCardCSVParser)


def _replace_nan_with_none(obj):
    """Recursively replace NaN/np.nan/float('nan') with None in dicts/lists/values."""
    if isinstance(obj, float) and (math.isnan(obj) or obj == np.nan):
        return None
    if isinstance(obj, dict):
        return {k: _replace_nan_with_none(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan_with_none(v) for v in obj]
    return obj


def main(input_path: str) -> ParserOutput:
    """
    Canonical entrypoint for contract-based integration. Parses a single Apple Card CSV and returns a ParserOutput.
    Accepts a single file path and returns a ParserOutput object. No directory or batch logic.
    """
    parser = AppleCardCSVParser()
    return parser.parse_file(input_path)
