import hashlib
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.utils.config import TRANSFORMATION_MAPS
import pandas as pd
import os


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


def normalize_parsed_data(file_path, parser_name, client_name=None, config=None):
    """
    Run the selected parser on a file and normalize the output to canonical transaction dicts.
    Adds a robust, deterministic transaction_id to each dict (SHA256 of date, amount, description, account).

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
    df["transaction_id"] = df.apply(compute_transaction_id, axis=1)

    # 4. Convert DataFrame to list of dicts
    return df.to_dict(orient="records")
