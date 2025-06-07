"""
Wells Fargo Checking CSV Parser (Modular)

- Parses Wells Fargo checking account CSV exports (sample header: Date, Amount, *, Check Number (optional), Description)
- Normalizes date and amount fields
- Outputs standardized schema: transaction_date, description, amount, source_file, source, transaction_type
- Robust to missing/malformed data

Requirements:
- Place in dataextractai/parsers/
- Inherit from BaseParser
- Register in ParserRegistry as 'wellsfargo_checking_csv'
- Implement parse_file and normalize_data
"""

import os
import pandas as pd
from datetime import datetime
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.utils.config import TRANSFORMATION_MAPS


class WellsFargoCheckingCSVParser(BaseParser):
    name = "wellsfargo_checking_csv"
    description = "Parser for Wells Fargo checking account CSV exports."
    file_types = [".csv"]

    @classmethod
    def can_parse(cls, file_path: str, sample_rows: list[str] = None, **kwargs) -> bool:
        try:
            df = pd.read_csv(file_path, nrows=1, header=None)
            expected = ["Date", "Amount", "*", "Check Number", "Description"]
            # Accept if first 2-3 columns match (Check Number is optional)
            actual = [str(c).strip() for c in df.iloc[0].tolist()]
            if actual[:2] == ["Date", "Amount"] and "Description" in actual:
                return True
        except Exception:
            pass
        return False

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

    def parse_file(self, input_path: str, config: dict = None) -> list[dict]:
        df = pd.read_csv(
            input_path,
            header=None,
            names=["date", "amount", "star", "check_number", "description"],
        )
        df["transaction_date"] = df["date"].apply(self.parse_date)
        df["amount"] = df["amount"].apply(self.parse_amount)
        df["description"] = df["description"].fillna("")
        records = []
        for _, row in df.iterrows():
            records.append(
                {
                    "transaction_date": row["transaction_date"],
                    "description": row["description"],
                    "amount": row["amount"],
                    "source_file": os.path.basename(input_path),
                    "file_path": input_path,
                    "file_name": os.path.basename(input_path),
                    "source": self.name,
                    "transaction_type": "Unknown",
                    "account_number": None,
                }
            )
        return records

    def normalize_data(self, raw_data: list[dict]) -> pd.DataFrame:
        # Use the transformation map for 'wellsfargo_bank_csv' (same as checking)
        tf_map = TRANSFORMATION_MAPS["wellsfargo_bank_csv"]
        normalized = []
        for row in raw_data:
            norm = {
                "transaction_date": row.get("transaction_date"),
                "description": row.get("description"),
                "amount": row.get("amount"),
                "source_file": row.get("source_file", ""),
                "file_path": row.get("file_path", ""),
                "file_name": row.get("file_name", ""),
                "source": row.get("source", self.name),
                "transaction_type": row.get("transaction_type", "Unknown"),
                "account_number": row.get("account_number", None),
            }
            normalized.append(norm)
        return pd.DataFrame(normalized)


ParserRegistry.register_parser(
    WellsFargoCheckingCSVParser.name, WellsFargoCheckingCSVParser
)
