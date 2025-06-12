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
from dataextractai.utils.utils import extract_date_from_filename
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)


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
    ) -> list[dict]:
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
        # --- Robust statement_date extraction ---
        statement_date = None
        statement_date_source = None
        # 1. Try original_filename
        if original_filename:
            statement_date = extract_date_from_filename(original_filename)
            if statement_date:
                statement_date_source = "original_filename"
                print(
                    f"[DEBUG] statement_date from original_filename: {statement_date}"
                )
        # 2. Try input filename
        if not statement_date:
            statement_date = extract_date_from_filename(file_path)
            if statement_date:
                statement_date_source = "filename"
                print(f"[DEBUG] statement_date from filename: {statement_date}")
        # 3. Try last row's transaction_date
        if not statement_date and not df.empty:
            last_row_date = df.iloc[-1]["transaction_date"]
            if last_row_date:
                statement_date = last_row_date
                statement_date_source = "last_row"
                print(f"[DEBUG] statement_date from last_row: {statement_date}")
        # 4. If still not found, None
        if not statement_date:
            print("[DEBUG] statement_date could not be determined; set to None")
        # Also get period start from first row if available
        statement_period_start = (
            df.iloc[0]["transaction_date"] if not df.empty else None
        )
        statement_period_end = statement_date
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
                    "file_path": file_path,
                    "debit": row["Debit"],
                    "credit": row["Credit"],
                    "statement_date": statement_date,
                    "statement_date_source": statement_date_source,
                    "statement_period_start": statement_period_start,
                    "statement_period_end": statement_period_end,
                    "account_number": None,
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
                "file_path": row.get("file_path", ""),
                "source": self.name,
                "transaction_type": (
                    "credit"
                    if str(row.get("category", "")).lower().startswith("payment")
                    or str(row.get("category", "")).lower().startswith("credit")
                    else "debit"
                ),
                "statement_date": row.get("statement_date"),
                "statement_period_start": row.get("statement_period_start"),
                "statement_period_end": row.get("statement_period_end"),
                "statement_date_source": row.get("statement_date_source"),
                "account_number": row.get("account_number"),
            }
            normalized.append(norm)
        return pd.DataFrame(normalized)


# Register the parser
ParserRegistry.register_parser(CapitalOneCSVParser.name, CapitalOneCSVParser)


def main(write_to_file=True, source_dir=None, output_csv=None, output_xlsx=None):
    import glob
    import pandas as pd
    import os

    parser = CapitalOneCSVParser()
    source_dir = source_dir or os.path.join(
        os.path.dirname(__file__), "../../data/clients/capitalone/input"
    )
    file_list = glob.glob(os.path.join(source_dir, "*.csv"))
    all_records = []
    for file_path in file_list:
        raw_data = parser.parse_file(
            file_path, original_filename=os.path.basename(file_path)
        )
        all_records.extend(raw_data)
    df = parser.normalize_data(all_records)
    # Build TransactionRecord list
    transactions = []
    for _, row in df.iterrows():
        transactions.append(
            TransactionRecord(
                transaction_date=row["transaction_date"],
                amount=row["amount"],
                description=row["description"],
                posted_date=row.get("posted_date"),
                transaction_type=row.get("transaction_type"),
                extra={
                    "card_no": row.get("card_no"),
                    "category": row.get("category"),
                    "source_file": row.get("source_file"),
                    "file_path": row.get("file_path"),
                    "debit": row.get("debit"),
                    "credit": row.get("credit"),
                },
            )
        )
    # Build StatementMetadata (use first record for metadata)
    metadata = None
    if not df.empty:
        metadata = StatementMetadata(
            statement_date=df.iloc[0].get("statement_date"),
            statement_period_start=df.iloc[0].get("statement_period_start"),
            statement_period_end=df.iloc[0].get("statement_period_end"),
            statement_date_source=df.iloc[0].get("statement_date_source"),
            original_filename=df.iloc[0].get("source_file"),
            account_number=df.iloc[0].get("account_number"),
            bank_name="Capital One",
            account_type="Credit Card",
            parser_name=CapitalOneCSVParser.name,
            parser_version=None,
            currency="USD",
            extra=None,
        )
    output = ParserOutput(
        transactions=transactions,
        metadata=metadata,
        schema_version="1.0",
        errors=None,
        warnings=None,
    )
    if write_to_file:
        if output_csv:
            df.to_csv(output_csv, index=False)
        if output_xlsx:
            df.to_excel(output_xlsx, index=False)
    return output
