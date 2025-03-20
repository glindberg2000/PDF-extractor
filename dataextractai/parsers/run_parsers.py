"""
run_parsers.py

This script is designed to sequentially execute a series of parser functions
for different types of financial documents. Each parser is responsible for
extracting transaction data from a specific format of PDF file and outputting
the results to a designated CSV and XLSX file.

The script assumes that each parser module has a `run` function that takes
no arguments and returns a pandas DataFrame containing the parsed data.
The script also assumes that the parsers write their output to the filesystem.

The script operates on the assumption that it is being run from the root
directory of the project, where the 'dataextractai' package can be found.
It also assumes that the required input files are located within the 'data/input'
directory, categorized into subdirectories by parser type (e.g., 'amazon', 'bofa_bank').

The output CSV and XLSX files are written to the 'data/output' directory,
following the same categorization as the input files.

Usage:
    To run all parsers and output to CSV and XLSX files:
    $ python  dataextractai/parsers/run_parsers.py

    To import and run parsers within another module:
    from scripts.run_parsers import run_all_parsers
    run_all_parsers()

The script's function is to streamline the process of running all parsers
and to ensure that the extracted data is saved in a consistent and
organized manner. This automation aids in maintaining a standardized
data processing pipeline.

Author: Gregory Lindberg
Date: November 5, 2023
"""

import os
import pandas as pd
from datetime import datetime  # Import the datetime class from the datetime module


# Import the parser functions
from dataextractai.parsers.wellsfargo_bank_parser import (
    run as run_wells_fargo_bank_parser,
)
from dataextractai.parsers.wellsfargo_mastercard_parser import (
    run as run_wells_fargo_mastercard_parser,
)
from dataextractai.parsers.wellsfargo_bank_csv_parser import (
    run as run_wells_fargo_bank_csv_parser,
)
from dataextractai.parsers.amazon_parser import run as run_amazon_parser
from dataextractai.parsers.bofa_bank_parser import run as run_bofa_bank_parser
from dataextractai.parsers.bofa_visa_parser import run as run_bofa_visa_parser
from dataextractai.parsers.chase_visa_parser import run as run_chase_visa_parser

# Add the data transformation function here
from dataextractai.utils.data_transformation import (
    apply_transformation_map as transform_to_core_structure,
)

from dataextractai.utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS

# SOURCE_DIR = PARSER_INPUT_DIRS["amazon"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["consolidated_core"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["consolidated_core"]["xlsx"]


def parse_date(date_str):
    """
    Parse a date string into a datetime object, handling different date formats.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):  # Add more formats here if needed
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unknown date format: {date_str}")


def has_files_to_parse(directory):
    """
    Check if the specified directory exists and contains any files.

    Args:
        directory (str): Path to the directory to check

    Returns:
        bool: True if directory exists and contains files, False otherwise
    """
    if not os.path.exists(directory):
        print(f"Directory does not exist: {directory}")
        return False

    files = [
        f
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and not f.startswith(".")  # Ignore hidden files
    ]
    if not files:
        print(f"No files found in directory: {directory}")
        return False

    return True


def run_all_parsers():
    print("Running all parsers...")

    # Dictionary to hold the dataframes from each parser
    dataframes = {}

    # Run Amazon parser
    print("\nRunning Amazon parser...")
    if has_files_to_parse(PARSER_INPUT_DIRS["amazon"]):
        dataframes["amazon"] = run_amazon_parser()
    else:
        dataframes["amazon"] = pd.DataFrame()

    # Run Bank of America bank parser
    print("\nRunning Bank of America bank parser...")
    if has_files_to_parse(PARSER_INPUT_DIRS["bofa_bank"]):
        dataframes["bofa_bank"] = run_bofa_bank_parser()
    else:
        dataframes["bofa_bank"] = pd.DataFrame()

    # Run Bank of America VISA parser
    print("\nRunning Bank of America VISA parser...")
    if has_files_to_parse(PARSER_INPUT_DIRS["bofa_visa"]):
        dataframes["bofa_visa"] = run_bofa_visa_parser()
    else:
        dataframes["bofa_visa"] = pd.DataFrame()

    # Run Chase VISA parser
    print("\nRunning Chase VISA parser...")
    if has_files_to_parse(PARSER_INPUT_DIRS["chase_visa"]):
        dataframes["chase_visa"] = run_chase_visa_parser()
    else:
        dataframes["chase_visa"] = pd.DataFrame()

    # Run Wells Fargo bank parser
    print("\nRunning Wells Fargo bank parser...")
    if has_files_to_parse(PARSER_INPUT_DIRS["wellsfargo_bank"]):
        dataframes["wellsfargo_bank"] = run_wells_fargo_bank_parser()
    else:
        dataframes["wellsfargo_bank"] = pd.DataFrame()

    # Run Wells Fargo MasterCard parser
    print("\nRunning Wells Fargo MasterCard parser...")
    if has_files_to_parse(PARSER_INPUT_DIRS["wellsfargo_mastercard"]):
        dataframes["wellsfargo_mastercard"] = run_wells_fargo_mastercard_parser()
    else:
        dataframes["wellsfargo_mastercard"] = pd.DataFrame()

    # Run Wells Fargo Bank CSV parser
    print("\nRunning Wells Fargo Bank CSV parser...")
    if has_files_to_parse(PARSER_INPUT_DIRS["wellsfargo_bank_csv"]):
        dataframes["wellsfargo_bank_csv"] = run_wells_fargo_bank_csv_parser()
    else:
        dataframes["wellsfargo_bank_csv"] = pd.DataFrame()

    print("\nAll parsers have been executed.")

    # Transform data to core data structure
    transformed_data = []
    for source, df in dataframes.items():
        # Check if the dataframe is not empty
        if not df.empty:
            print(f"transforming: {source} ")
            # Transform and append the dataframe to the transformed_data list
            transformed_data.append(transform_to_core_structure(df, source))

    # Combine all transformed data
    if transformed_data:
        combined_df = pd.concat(transformed_data, ignore_index=True)
        # Sort by date
        combined_df = combined_df.sort_values("transaction_date")
        # Save to CSV and Excel
        combined_df.to_csv(OUTPUT_PATH_CSV, index=False)
        combined_df.to_excel(OUTPUT_PATH_XLSX, index=False)
        print(f"\nTotal transactions processed: {len(combined_df)}")
        return combined_df
    else:
        print("\nNo transactions were processed.")
        return pd.DataFrame()


if __name__ == "__main__":
    run_all_parsers()
