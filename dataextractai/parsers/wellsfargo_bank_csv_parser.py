"""
Wells Fargo Bank CSV Parser

This module parses Wells Fargo bank account CSV exports.
The CSV format is expected to have the following columns:
- Date
- Amount
- * (unused)
- Check Number (optional)
- Description

Author: Gregory Lindberg
Date: March 2024
"""

import os
import pandas as pd
from datetime import datetime
from dataextractai.utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from dataextractai.utils.utils import extract_date_from_filename
from dateutil import parser as dateutil_parser
import math
import numpy as np
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)

SOURCE_DIR = PARSER_INPUT_DIRS["wellsfargo_bank_csv"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["wellsfargo_bank_csv"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["wellsfargo_bank_csv"]["xlsx"]


def parse_amount(amount_str):
    """Convert string amount to float, handling parentheses for negative numbers."""
    try:
        # If it's already a float, return it
        if isinstance(amount_str, (int, float)):
            return float(amount_str)
        # If it's a string, process it
        return float(str(amount_str).replace(",", ""))
    except (ValueError, TypeError):
        return 0.0


def parse_date(date_str):
    """Parse date string in MM/DD/YYYY format."""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def process_csv_file(file_path, original_filename=None):
    """
    Process a single Wells Fargo CSV file.

    Args:
        file_path (str): Path to the CSV file
        original_filename (str, optional): Original filename if available

    Returns:
        pandas.DataFrame: Processed data in standardized format
    """
    # Read CSV file
    df = pd.read_csv(
        file_path,
        header=None,
        names=["date", "amount", "star", "check_number", "description"],
    )

    # Convert date strings to standard format
    df["transaction_date"] = df["date"].apply(parse_date)

    # Convert amounts to float
    df["amount"] = df["amount"].apply(parse_amount)

    # Clean up description
    df["description"] = df["description"].fillna("")

    # --- Robust statement_date extraction ---
    statement_date = None
    date_source = None
    # 1. Try original_filename
    if original_filename:
        statement_date = extract_date_from_filename(original_filename)
        date_source = "original_filename"
        if statement_date:
            print(f"[DEBUG] statement_date from original_filename: {statement_date}")
    # 2. Try input filename
    if not statement_date:
        statement_date = extract_date_from_filename(file_path)
        date_source = "input_path"
        if statement_date:
            print(f"[DEBUG] statement_date from input_path: {statement_date}")
    # 3. Try date range in file (last transaction_date)
    valid_dates = [d for d in df["transaction_date"] if d]
    if not statement_date and valid_dates:
        statement_date = valid_dates[-1]
        date_source = "last_row"
        print(f"[DEBUG] statement_date from last_row: {statement_date}")
    # Validate date
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
    # Create standardized DataFrame with minimal required fields
    result_df = pd.DataFrame(
        {
            "transaction_date": df["transaction_date"],
            "description": df["description"],
            "amount": df["amount"],
            "source_file": os.path.basename(file_path),
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "source": "wellsfargo_bank_csv",
            "transaction_type": "Unknown",  # Will be categorized later
            "account_number": None,
            "statement_date": statement_date,
            "statement_date_source": date_source,
            "statement_period_start": valid_dates[0] if valid_dates else None,
            "statement_period_end": valid_dates[-1] if valid_dates else None,
        }
    )

    return result_df


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
    Canonical entrypoint for contract-based integration. Parses a single Wells Fargo Bank CSV and returns a ParserOutput.
    Accepts a single file path and returns a ParserOutput object. No directory or batch logic.
    All transaction_date and metadata date fields are normalized to YYYY-MM-DD format.
    """
    errors = []
    warnings = []
    try:
        df = process_csv_file(
            input_path, original_filename=os.path.basename(input_path)
        )
        transactions = []
        for idx, row in df.iterrows():
            try:
                # Normalize transaction_date
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
                        "check_number": row.get("check_number"),
                        "source_file": row.get("source_file"),
                        "file_path": row.get("file_path"),
                    },
                )
                transactions.append(tr)
            except Exception as e:
                import traceback

                tb = traceback.format_exc()
                msg = f"TransactionRecord validation error at row {idx} in {input_path}: {e}\n{tb}"
                errors.append(msg)
        # Normalize metadata date fields
        meta = df.iloc[0] if not df.empty else {}

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
            parser_name="wellsfargo_bank_csv",
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
        # Final Pydantic validation
        try:
            ParserOutput.model_validate(output.model_dump())
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            msg = f"Final ParserOutput validation error: {e}\n{tb}"
            errors.append(msg)
            output.errors = errors
            raise
        # Clean up NaN values in the output dict
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


if __name__ == "__main__":
    main()
