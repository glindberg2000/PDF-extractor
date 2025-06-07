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
from typing import Any
from datetime import datetime
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry


class CapitalOneCSVParser(BaseParser):
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
        """
        Detects if the file is a CapitalOne CSV by checking for required headers.
        """
        try:
            df = pd.read_csv(file_path, nrows=1)
            headers = set(df.columns.str.strip())
            return (
                len(cls.REQUIRED_HEADERS.intersection(headers)) >= 5
            )  # Allow for minor header variations
        except Exception:
            return False

    def parse_file(self, file_path: str, config: dict = None) -> list[dict]:
        """
        Parses the CapitalOne CSV file and returns a normalized DataFrame.
        """
        df = pd.read_csv(file_path)
        df.columns = [c.strip() for c in df.columns]
        # Map columns to normalized names
        colmap = {
            "Transaction Date": "transaction_date",
            "Posted Date": "posted_date",
            "Card No.": "card_no",
            "Description": "description",
            "Category": "category",
            "Debit": "debit",
            "Credit": "credit",
        }
        for k in colmap:
            if k not in df.columns:
                df[k] = None
        # Normalize dates
        for date_col, norm_col in [
            ("Transaction Date", "transaction_date"),
            ("Posted Date", "posted_date"),
        ]:
            df[norm_col] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime(
                "%Y-%m-%d"
            )

        # Combine Debit and Credit into amount
        def compute_amount(row):
            debit = row.get("Debit")
            credit = row.get("Credit")
            try:
                if pd.notnull(debit) and debit != "":
                    return float(debit)
                elif pd.notnull(credit) and credit != "":
                    return -float(credit)
            except Exception:
                return None
            return None

        df["amount"] = df.apply(compute_amount, axis=1)
        # Drop rows with no amount or transaction_date
        df = df.dropna(subset=["amount", "transaction_date"])
        # Build output dicts with normalized keys
        records = []
        for _, row in df.iterrows():
            records.append(
                {
                    "transaction_date": row["transaction_date"],
                    "posted_date": row["posted_date"],
                    "card_no": row["Card No."],
                    "description": row["Description"],
                    "category": row["Category"],
                    "amount": row["amount"],
                    "source_file": os.path.basename(file_path),
                    "debit": row["Debit"],
                    "credit": row["Credit"],
                }
            )
        return records

    def normalize_data(self, raw_data: list[dict]) -> pd.DataFrame:
        normalized = []
        for row in raw_data:
            norm = {
                "transaction_date": row.get("transaction_date"),
                "posted_date": row.get("posted_date"),
                "card_no": row.get("card_no"),
                "description": row.get("description"),
                "category": row.get("category"),
                "amount": row.get("amount"),
                "source_file": row.get("source_file", ""),
                "source": self.name,
                "transaction_type": (
                    "credit"
                    if str(row.get("category", "")).lower().startswith("payment")
                    or str(row.get("category", "")).lower().startswith("credit")
                    else "debit"
                ),
            }
            normalized.append(norm)
        return pd.DataFrame(normalized)


# Register the parser
ParserRegistry.register_parser(CapitalOneCSVParser.name, CapitalOneCSVParser)
