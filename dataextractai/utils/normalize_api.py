import hashlib
import logging
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.utils.config import TRANSFORMATION_MAPS
import pandas as pd
import os
from dataextractai.utils.utils import standardize_column_names
from dataextractai.parsers_core.autodiscover import autodiscover_parsers

# Register all available parsers at import time
autodiscover_parsers()

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ["transaction_date", "description", "amount"]


def compute_transaction_id(row):
    """
    Compute a deterministic transaction_id hash from key fields.
    Uses date, amount, description, and account_number if present.
    """
    key_fields = [
        str(row.get("transaction_date", "")),
        str(row.get("amount", "")),
        str(row.get("description", "")),
        str(row.get("account_number", "")),
    ]
    key_str = "|".join(key_fields)
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


def is_valid_transaction(tx):
    """
    Check if a transaction dict has all required fields as valid strings (not None/NaN/empty).
    """
    for field in REQUIRED_FIELDS:
        value = tx.get(field, None)
        if (
            value is None
            or (isinstance(value, float) and pd.isna(value))
            or str(value).strip() == ""
        ):
            return False, f"Missing or invalid field: {field}"
        if field == "transaction_date":
            # Must be a string in YYYY-MM-DD or similar format
            if not isinstance(value, str):
                return False, f"transaction_date is not a string: {value}"
            try:
                pd.to_datetime(value)
            except Exception:
                return False, f"transaction_date not parseable: {value}"
    return True, None


def normalize_parsed_data(file_path, parser_name, client_name=None, config=None):
    """
    Run the selected parser on a file and normalize the output to canonical transaction dicts.
    Adds a robust, deterministic transaction_id to each dict (SHA256 of date, amount, description, account).
    Skips and logs any transactions with missing/invalid required fields (transaction_date, description, amount).

    Args:
        file_path (str): Path to the statement file (PDF, CSV, etc.)
        parser_name (str): Name of the parser to use (must be registered)
        client_name (str, optional): Client name for context (used for transformation map selection)
        config (dict, optional): Additional config for the parser

    Returns:
        List[dict]: List of canonical transaction dicts ready for DB insertion, each with a transaction_id
    """
    # 1. Get and run the parser
    parser_cls = ParserRegistry.get_parser(parser_name)
    if parser_cls is None:
        raise ValueError(f"Parser '{parser_name}' not found in registry.")
    parser = parser_cls()
    raw_data = parser.parse_file(file_path, config=config)
    df = parser.normalize_data(raw_data)

    # Always standardize column names before transformation
    df = standardize_column_names(df)

    # 2. Apply transformation map if available
    source = parser_name
    if client_name:
        # Optionally use client_name for more specific transformation
        source = client_name
    transform_map = TRANSFORMATION_MAPS.get(
        source, TRANSFORMATION_MAPS.get(parser_name)
    )
    if transform_map:
        transformed_df = pd.DataFrame()
        for target_col, source_col in transform_map.items():
            if callable(source_col):
                transformed_df[target_col] = df.apply(source_col, axis=1)
            elif source_col in df.columns:
                transformed_df[target_col] = df[source_col]
            else:
                transformed_df[target_col] = None
        df = transformed_df

    # 3. Add deterministic transaction_id
    df["transaction_hash"] = df.apply(compute_transaction_id, axis=1)

    # 4. Validate and filter transactions
    valid_transactions = []
    for tx in df.to_dict(orient="records"):
        is_valid, reason = is_valid_transaction(tx)
        if is_valid:
            valid_transactions.append(tx)
        else:
            logger.warning(f"Skipping transaction: {reason} | Data: {tx}")

    # After all other normalization steps, ensure required fields are present
    if "source" not in df.columns:
        df["source"] = parser_name
    else:
        df["source"] = parser_name  # Overwrite to ensure consistency
    if "file_path" not in df.columns:
        df["file_path"] = file_path
    else:
        df["file_path"] = df["file_path"].fillna(file_path)
    base_file_name = os.path.basename(file_path)
    df["file_name"] = base_file_name

    return valid_transactions


def normalize_parsed_data_df(file_path, parser_name, client_name=None, config=None):
    """
    Parse and normalize a single statement file in one step, returning a pandas DataFrame of valid, standardized transactions.

    This is the recommended function for downstream use (Django, data science, etc.).
    It preserves all original and mapped columns, including statement_year/month for robust date normalization.

    Args:
        file_path (str): Path to the statement file (PDF, CSV, etc.)
        parser_name (str): Name of the parser to use (must be registered, e.g. 'chase_checking')
        client_name (str, optional): Client name for context (used for transformation map selection, e.g. 'chase_test')
        config (dict, optional): Additional config for the parser (rarely needed; statement_date is inferred from filename)

    Returns:
        pd.DataFrame: DataFrame of valid, canonical transaction rows (with all context columns preserved)

    Example:
        import dataextractai.parsers.chase_checking_parser  # Ensure parser is registered
        from dataextractai.utils.normalize_api import normalize_parsed_data_df
        df = normalize_parsed_data_df(
            "data/clients/chase_test/input/chase_visa/20240612-statements-7429-.pdf",
            "chase_checking",
            "chase_test"
        )
        print(df.head())
        print(df.columns)
        print(f"Rows: {len(df)}")
    """
    parser_cls = ParserRegistry.get_parser(parser_name)
    if parser_cls is None:
        raise ValueError(f"Parser '{parser_name}' not found in registry.")
    parser = parser_cls()
    raw_data = parser.parse_file(file_path, config=config)
    print("[DEBUG] Raw data:", raw_data)
    df = parser.normalize_data(raw_data)
    print("[DEBUG] After normalize_data:", df.head(), df.columns, df.shape)
    df = standardize_column_names(df)
    print("[DEBUG] After standardize_column_names:", df.head(), df.columns, df.shape)

    source = client_name if client_name else parser_name
    transform_map = TRANSFORMATION_MAPS.get(
        source, TRANSFORMATION_MAPS.get(parser_name)
    )
    if transform_map:
        # Start with a copy of all columns, then overwrite/add mapped columns
        transformed_df = df.copy()
        for target_col, source_col in transform_map.items():
            if callable(source_col):
                transformed_df[target_col] = df.apply(source_col, axis=1)
            elif source_col in df.columns:
                transformed_df[target_col] = df[source_col]
            else:
                transformed_df[target_col] = None
        df = transformed_df
        print("[DEBUG] After transformation map:", df.head(), df.columns, df.shape)

    # --- PATCH: Normalize transaction_date to YYYY-MM-DD (match CLI) ---
    def normalize_date(row):
        date_str = row.get("transaction_date", None)
        if pd.isna(date_str) or not date_str:
            return pd.NaT
        # Try to parse as YYYY-MM-DD first
        try:
            date = pd.to_datetime(date_str, format="%Y-%m-%d", errors="coerce")
            if not pd.isna(date):
                return date
        except Exception:
            pass
        # Try MM/DD with statement_year if available
        try:
            if "statement_year" in row and row["statement_year"]:
                year = int(row["statement_year"])
                # Accept MM/DD or M/D
                m, d = [int(x) for x in str(date_str).split("/")]
                return pd.Timestamp(year=year, month=m, day=d)
        except Exception:
            pass
        # Try generic parsing
        try:
            date = pd.to_datetime(date_str, errors="coerce")
            if not pd.isna(date):
                return date
        except Exception:
            pass
        return pd.NaT

    if "transaction_date" in df.columns:
        df["normalized_date"] = df.apply(normalize_date, axis=1)
        # Overwrite transaction_date with normalized value (YYYY-MM-DD)
        df["transaction_date"] = df["normalized_date"].apply(
            lambda x: x.strftime("%Y-%m-%d") if pd.notnull(x) else None
        )
        print("[DEBUG] After date normalization:", df.head(), df.columns, df.shape)

    # Compute and add transaction_hash (SHA256) for deduplication
    df["transaction_hash"] = df.apply(compute_transaction_id, axis=1)
    # Do NOT overwrite or create 'transaction_id' unless present in the data

    # Validate and filter transactions
    valid_mask = df.apply(lambda row: is_valid_transaction(row)[0], axis=1)
    print("[DEBUG] Validation mask:", valid_mask.value_counts())
    valid_df = df[valid_mask].reset_index(drop=True)
    print(
        "[DEBUG] After validation:", valid_df.head(), valid_df.columns, valid_df.shape
    )

    # After all other normalization steps, ensure required fields are present (forcibly, for robustness)
    if "source" not in df.columns:
        df["source"] = parser_name
    else:
        df["source"] = parser_name  # Overwrite to ensure consistency
    if "file_path" not in df.columns:
        df["file_path"] = file_path
    else:
        df["file_path"] = df["file_path"].fillna(file_path)
    base_file_name = os.path.basename(file_path)
    df["file_name"] = base_file_name
    print(f"[DEBUG] Final DataFrame columns: {df.columns.tolist()}")
    return df
