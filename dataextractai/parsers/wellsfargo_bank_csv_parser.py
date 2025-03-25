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


def process_csv_file(file_path):
    """
    Process a single Wells Fargo CSV file.

    Args:
        file_path (str): Path to the CSV file

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

    # Create standardized DataFrame with minimal required fields
    result_df = pd.DataFrame(
        {
            "transaction_date": df["transaction_date"],
            "description": df["description"],
            "amount": df["amount"],
            "source_file": os.path.basename(file_path),
            "source": "wellsfargo_bank_csv",
            "transaction_type": "Unknown",  # Will be categorized later
        }
    )

    return result_df


def run(input_dir=None, output_paths=None, write_to_file=True):
    """
    Run the Wells Fargo CSV parser on all files in the source directory.

    Args:
        input_dir (str, optional): Directory containing CSV files. If None, uses default.
        output_paths (dict, optional): Dictionary containing output paths. If None, uses default.
        write_to_file (bool, optional): Whether to write results to file. Default is True.

    Returns:
        pandas.DataFrame: Combined data from all processed files
    """
    all_data = []

    # Use provided paths or fall back to defaults
    source_dir = input_dir if input_dir is not None else SOURCE_DIR

    if output_paths is not None:
        output_csv = (
            output_paths["csv"] if output_paths is not None else OUTPUT_PATH_CSV
        )
        output_xlsx = (
            output_paths["xlsx"] if output_paths is not None else OUTPUT_PATH_XLSX
        )
    else:
        output_csv = OUTPUT_PATH_CSV
        output_xlsx = OUTPUT_PATH_XLSX

    # Process each CSV file in the source directory
    for filename in os.listdir(source_dir):
        if filename.endswith(".csv"):
            file_path = os.path.join(source_dir, filename)
            try:
                df = process_csv_file(file_path)
                all_data.append(df)
                print(f"Successfully processed {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")

    if not all_data:
        return pd.DataFrame()

    # Combine all processed data
    combined_df = pd.concat(all_data, ignore_index=True)

    # Sort by date
    combined_df = combined_df.sort_values("transaction_date")

    # Export to CSV and XLSX if write_to_file is True
    if write_to_file:
        combined_df.to_csv(output_csv, index=False)
        combined_df.to_excel(output_xlsx, index=False)

    return combined_df


if __name__ == "__main__":
    run()
