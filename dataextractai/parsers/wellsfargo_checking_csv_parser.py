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
import re
from dataextractai.utils.utils import extract_date_from_filename
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)
import math
import numpy as np


class WellsFargoCheckingCSVParser(BaseParser):
    """
    Parser for Wells Fargo checking account CSV exports.

    Statement date extraction should prioritize content-based extraction (if available in future formats), only falling back to filename if content-based extraction fails. If both fail, set to None. Currently, statement_date is set to None for all records.
    """

    name = "wellsfargo_checking_csv"
    description = "Parser for Wells Fargo checking account CSV exports."
    file_types = [".csv"]

    @staticmethod
    def _match_csv_headers(file_path, required_headers, min_matches=2):
        try:
            df = pd.read_csv(file_path, nrows=1)
            headers = set([str(h).strip().lower() for h in df.columns])
            required = set([h.lower() for h in required_headers])
            return len(headers & required) >= min_matches
        except Exception:
            return False

    @classmethod
    def can_parse(cls, file_path: str, sample_rows: list[str] = None, **kwargs) -> bool:
        try:
            df = pd.read_csv(file_path, nrows=1, header=None)
            row = df.iloc[0].tolist()
            if len(row) != 5:
                return False
            if str(row[2]).strip() != "*":
                return False
            date_re = re.compile(r"\d{1,2}/\d{1,2}/\d{4}")
            if not date_re.fullmatch(str(row[0]).strip()):
                return False
            try:
                float(row[1])
            except Exception:
                return False
            # 4th column can be blank or a number, 5th is string (no strict check needed)
            return True
        except Exception:
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

    def parse_file(
        self, input_path: str, config: dict = None, original_filename: str = None
    ) -> list[dict]:
        df = pd.read_csv(
            input_path,
            header=None,
            names=["date", "amount", "star", "check_number", "description"],
        )
        df["transaction_date"] = df["date"].apply(self.parse_date)
        df["amount"] = df["amount"].apply(self.parse_amount)
        df["description"] = df["description"].fillna("")
        # --- Robust statement_date extraction ---
        statement_date = None
        date_source = None
        # 1. Try original_filename
        if original_filename:
            statement_date = extract_date_from_filename(original_filename)
            date_source = "original_filename"
            if statement_date:
                print(
                    f"[DEBUG] statement_date from original_filename: {statement_date}"
                )
        # 2. Try input filename
        if not statement_date:
            statement_date = extract_date_from_filename(input_path)
            date_source = "input_path"
            if statement_date:
                print(f"[DEBUG] statement_date from input_path: {statement_date}")
        # 3. Try date range in file (first and last transaction_date)
        if not statement_date:
            valid_dates = [d for d in df["transaction_date"] if d]
            if valid_dates:
                first_date = valid_dates[0]
                last_date = valid_dates[-1]
                # Use last_date as statement_date, but also expose both as period
                statement_date = last_date
                date_source = "last_row"
                print(f"[DEBUG] statement_date from last_row: {statement_date}")
        # Validate date
        from dateutil import parser as dateutil_parser

        try:
            if statement_date:
                _ = dateutil_parser.parse(statement_date)
            else:
                statement_date = None
        except Exception:
            print(
                f"[DEBUG] Extracted statement_date is not a valid date: {statement_date}. Setting to None."
            )
            statement_date = None
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
                    "statement_date": statement_date,  # Now robustly extracted
                    "statement_period_start": valid_dates[0] if valid_dates else None,
                    "statement_period_end": valid_dates[-1] if valid_dates else None,
                    "statement_date_source": date_source,
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

    def main(
        self, write_to_file=True, source_dir=None, output_csv=None, output_xlsx=None
    ):
        import glob
        import pandas as pd
        import os

        source_dir = source_dir or os.path.join(
            os.path.dirname(__file__), "../../data/clients/wellsfargo_checking/input"
        )
        file_list = glob.glob(os.path.join(source_dir, "*.csv"))
        all_outputs = []
        for file_path in file_list:
            raw_data = self.parse_file(
                file_path, original_filename=os.path.basename(file_path)
            )
            df = self.normalize_data(raw_data)
            # Build transactions list
            transactions = [
                TransactionRecord(
                    transaction_date=row.get("transaction_date"),
                    amount=row.get("amount"),
                    description=row.get("description"),
                    posted_date=None,
                    transaction_type=row.get("transaction_type"),
                    extra={
                        k: v
                        for k, v in row.items()
                        if k
                        not in [
                            "transaction_date",
                            "amount",
                            "description",
                            "transaction_type",
                        ]
                    },
                )
                for _, row in df.iterrows()
            ]
            # Build metadata
            metadata = StatementMetadata(
                statement_date=raw_data[0].get("statement_date") if raw_data else None,
                statement_period_start=(
                    raw_data[0].get("statement_period_start") if raw_data else None
                ),
                statement_period_end=(
                    raw_data[0].get("statement_period_end") if raw_data else None
                ),
                statement_date_source=(
                    raw_data[0].get("statement_date_source") if raw_data else None
                ),
                original_filename=os.path.basename(file_path),
                account_number=raw_data[0].get("account_number") if raw_data else None,
                bank_name="Wells Fargo",
                account_type="Checking",
                parser_name=self.name,
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
            all_outputs.append(output)
            # Optionally write DataFrame to CSV/XLSX for CLI/legacy
            if write_to_file:
                if output_csv:
                    df.to_csv(output_csv, index=False)
                if output_xlsx:
                    df.to_excel(output_xlsx, index=False)
        return all_outputs if len(all_outputs) > 1 else all_outputs[0]


ParserRegistry.register_parser(
    WellsFargoCheckingCSVParser.name, WellsFargoCheckingCSVParser
)


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
    Canonical entrypoint for contract-based integration. Parses a single Wells Fargo Checking CSV and returns a ParserOutput.
    Accepts a single file path and returns a ParserOutput object. No directory or batch logic.
    All transaction_date and metadata date fields are normalized to YYYY-MM-DD format.
    """
    errors = []
    warnings = []
    try:
        parser = WellsFargoCheckingCSVParser()
        raw_data = parser.parse_file(
            input_path, original_filename=os.path.basename(input_path)
        )
        df = parser.normalize_data(raw_data)
        transactions = []
        for idx, row in df.iterrows():
            try:
                t_date = row.get("transaction_date")
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
                tr = TransactionRecord(
                    transaction_date=t_date,
                    amount=row.get("amount"),
                    description=row.get("description"),
                    posted_date=None,
                    transaction_type=row.get("transaction_type"),
                    extra={
                        k: v
                        for k, v in row.items()
                        if k
                        not in [
                            "transaction_date",
                            "amount",
                            "description",
                            "transaction_type",
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
            statement_date=norm_date(meta.get("statement_date")),
            statement_period_start=norm_date(meta.get("statement_period_start")),
            statement_period_end=norm_date(meta.get("statement_period_end")),
            statement_date_source=meta.get("statement_date_source"),
            original_filename=os.path.basename(input_path),
            account_number=meta.get("account_number"),
            bank_name="Wells Fargo",
            account_type="Checking",
            parser_name="wellsfargo_checking_csv",
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
