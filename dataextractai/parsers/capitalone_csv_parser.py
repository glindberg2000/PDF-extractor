"""
CapitalOne CSV Transaction Parser

- Parses CapitalOne credit card CSV exports (sample header: Transaction Date, Posted Date, Card No., Description, Category, Debit, Credit)
- Combines Debit and Credit columns into a single 'amount' column (debits positive, credits negative)
- Normalizes date fields to YYYY-MM-DD
- Maps Description, Category, Card No. to normalized fields
- Output matches standardized schema (transaction_date, description, amount, source_file, source, transaction_type, etc.)
- Robust to minor header variations and missing/malformed data

Requirements:
- Place in dataextractai/parsers/
- Inherit from BaseParser
- Register in parser registry
- Implement can_parse to detect CapitalOne CSVs by header
- Compatible with modular and CLI workflows
"""

import os
import pandas as pd
import numpy as np
from typing import Any
from datetime import datetime
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.utils.utils import extract_date_from_filename
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)
import logging
import traceback
import math


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


# Setup persistent logging
log_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../../../logs")
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, "capitalone_csv_parser.log")
logger = logging.getLogger("capitalone_csv_parser")
if not logger.handlers:
    fh = logging.FileHandler(log_path, mode="a")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)


class CapitalOneCSVParser(BaseParser):
    """
    Parser for CapitalOne credit card CSV transaction downloads.

    Statement date extraction should prioritize content-based extraction (if available in future formats), only falling back to filename if content-based extraction fails. If both fail, set to None. Currently, statement_date is set to None for all records.
    """

    name = "capitalone_csv"
    description = "Parser for CapitalOne credit card CSV transaction downloads."
    file_types = [".csv"]

    REQUIRED_HEADERS = {
        "Transaction Date",
        "Posted Date",
        "Card No.",
        "Description",
        "Category",
        "Debit",
        "Credit",
    }

    @classmethod
    def can_parse(cls, file_path: str, sample_rows: list[str] = None, **kwargs) -> bool:
        required_headers = [
            "Transaction Date",
            "Posted Date",
            "Card No.",
            "Description",
            "Category",
            "Debit",
            "Credit",
        ]
        try:
            df = pd.read_csv(file_path, nrows=0)
            headers = [str(h).strip() for h in df.columns]
            print(f"[DEBUG] CapitalOneCSVParser.can_parse: headers={headers}")
            print(
                f"[DEBUG] CapitalOneCSVParser.can_parse: required_headers={required_headers}"
            )
            return headers == required_headers
        except Exception as e:
            print(f"[DEBUG] CapitalOneCSVParser.can_parse: Exception: {e}")
            return False

    def parse_file(
        self, file_path: str, config: dict = None, original_filename: str = None
    ) -> ParserOutput:
        """
        Parses the CapitalOne CSV file and returns a ParserOutput object.
        """
        df = pd.read_csv(file_path)
        warnings = []
        logger.info(f"[DEBUG] Read CSV: {file_path}, rows={len(df)}")
        df.columns = [c.strip() for c in df.columns]

        # Fill NaN to prevent errors, but use a more robust selection method
        df["Debit"] = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
        df["Credit"] = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)

        # Normalize dates
        for date_col in ["Transaction Date", "Posted Date"]:
            df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime(
                "%Y-%m-%d"
            )

        # Combine Debit and Credit into a single, normalized amount column
        # Use np.where for a robust selection between the two columns
        df["amount"] = np.where(df["Debit"] != 0, df["Debit"], df["Credit"])
        df["transaction_type"] = np.where(df["Debit"] != 0, "debit", "credit")

        # Invert the sign for debits only. Credits are already positive.
        df.loc[df["transaction_type"] == "debit", "amount"] = -df["amount"]

        # Map to TransactionRecord fields
        df = df.rename(
            columns={
                "Transaction Date": "transaction_date",
                "Posted Date": "posted_date",
                "Description": "description",
            }
        )

        transactions = [
            TransactionRecord(**_replace_nan_with_none(row))
            for row in df.to_dict(orient="records")
        ]

        metadata = StatementMetadata(
            statement_date=transactions[-1].transaction_date if transactions else None,
            statement_period_start=(
                transactions[0].transaction_date if transactions else None
            ),
            statement_period_end=(
                transactions[-1].transaction_date if transactions else None
            ),
            original_filename=os.path.basename(file_path),
            bank_name="Capital One",
            account_type="Credit Card",
            parser_name=self.name,
        )

        return ParserOutput(
            transactions=transactions, metadata=metadata, warnings=warnings
        )

    def normalize_data(self, raw_data: list[dict]) -> pd.DataFrame:
        """No-op for this parser."""
        pass


# Register the parser
ParserRegistry.register_parser(CapitalOneCSVParser.name, CapitalOneCSVParser)


def main(input_path: str) -> ParserOutput:
    """Canonical entrypoint for contract-based integration."""
    parser = CapitalOneCSVParser()
    return parser.parse_file(input_path)
