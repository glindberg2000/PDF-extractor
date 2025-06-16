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
    All transaction_date and metadata date fields are normalized to YYYY-MM-DD format.
    """
    errors = []
    warnings = []
    try:
        parser = AppleCardCSVParser()
        raw_data = parser.parse_file(
            input_path, original_filename=os.path.basename(input_path)
        )
        df = parser.normalize_data(raw_data)
        transactions = []
        for idx, row in df.iterrows():
            try:
                t_date = row.get("transaction_date")
                p_date = row.get("post_date")
                if t_date:
                    try:
                        t_date = datetime.strptime(t_date, "%Y-%m-%d").strftime(
                            "%Y-%m-%d"
                        )
                    except Exception:
                        warnings.append(
                            f"[WARN] Could not normalize transaction_date '{t_date}' at row {idx} in {input_path}"
                        )
                        t_date = None
                if p_date:
                    try:
                        p_date = datetime.strptime(p_date, "%Y-%m-%d").strftime(
                            "%Y-%m-%d"
                        )
                    except Exception:
                        warnings.append(
                            f"[WARN] Could not normalize post_date '{p_date}' at row {idx} in {input_path}"
                        )
                        p_date = None
                tr = TransactionRecord(
                    transaction_date=t_date,
                    amount=row.get("amount"),
                    description=row.get("description"),
                    posted_date=p_date,
                    transaction_type=row.get("type"),
                    extra={
                        k: v
                        for k, v in row.items()
                        if k
                        not in [
                            "transaction_date",
                            "amount",
                            "description",
                            "transaction_type",
                            "post_date",
                        ]
                    },
                )
                transactions.append(tr)
            except Exception as e:
                import traceback

                tb = traceback.format_exc()
                msg = f"TransactionRecord validation error at row {idx} in {input_path}: {e}\n{tb}"
                errors.append(msg)
        meta = raw_data[0] if raw_data else {}

        def norm_date(val):
            if not val:
                return None
            try:
                return datetime.strptime(val, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                warnings.append(
                    f"[WARN] Could not normalize metadata date '{val}' in {input_path}"
                )
                return None

        metadata = StatementMetadata(
            statement_date=None,  # Apple Card CSV does not have a statement date field
            statement_period_start=None,
            statement_period_end=None,
            statement_date_source=None,
            original_filename=os.path.basename(input_path),
            account_number=None,
            bank_name="Apple Card",
            account_type="Credit Card",
            parser_name="apple_card_csv",
            parser_version=None,
            currency="USD",
            extra=None,
        )
        output = ParserOutput(
            transactions=transactions,
            metadata=metadata,
            schema_version="1.0",
            errors=errors if errors else None,
            warnings=warnings if warnings else None,
        )
        try:
            ParserOutput.model_validate(output.model_dump())
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            msg = f"Final ParserOutput validation error: {e}\n{tb}"
            errors.append(msg)
            output.errors = errors
            raise
        output_dict = output.model_dump()
        output_dict = _replace_nan_with_none(output_dict)
        print("[DEBUG] Cleaned ParserOutput sample:", output_dict)
        return ParserOutput.model_validate(output_dict)
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        msg = f"[FATAL] Error in main() for {input_path}: {e}\n{tb}"
        print(msg)
        return ParserOutput(
            transactions=[],
            metadata=None,
            schema_version="1.0",
            errors=[msg],
            warnings=None,
        )
