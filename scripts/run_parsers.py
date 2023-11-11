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
    $ python -m scripts.run_parsers

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


def run_all_parsers():
    print("Running all parsers...")

    # Dictionary to hold the dataframes from each parser
    dataframes = {}

    # Run Amazon parser
    print("\nRunning Amazon parser...")
    dataframes["amazon"] = run_amazon_parser()

    # Run Bank of America bank parser
    print("\nRunning Bank of America bank parser...")
    dataframes["bofa_bank"] = run_bofa_bank_parser()

    # Run Bank of America VISA parser
    print("\nRunning Bank of America VISA parser...")
    dataframes["bofa_visa"] = run_bofa_visa_parser()

    # Run Chase VISA parser
    print("\nRunning Chase VISA parser...")
    dataframes["chase_visa"] = run_chase_visa_parser()

    # Run Wells Fargo bank parser
    print("\nRunning Wells Fargo bank parser...")
    dataframes["wellsfargo_bank"] = run_wells_fargo_bank_parser()

    # Run Wells Fargo MasterCard parser
    print("\nRunning Wells Fargo MasterCard parser...")
    dataframes["wellsfargo_mastercard"] = run_wells_fargo_mastercard_parser()

    print("\nAll parsers have been executed.")

    # Transform data to core data structure
    transformed_data = []
    for source, df in dataframes.items():
        # Check if the dataframe is not empty
        if not df.empty:
            print(f"transforming: {source} ")
            # Transform and append the dataframe to the transformed_data list
            transformed_data.append(transform_to_core_structure(df, source))

    # Concatenate all transformed data into a single dataframe
    if transformed_data:
        transformed_data = pd.concat(transformed_data, ignore_index=True)
    else:
        transformed_data = pd.DataFrame()

    # Sort the DataFrame by 'transaction_date'
    # First standardize the dates
    # Convert and standardize 'transaction_date' to datetime objects
    transformed_data["transaction_date"] = transformed_data["transaction_date"].apply(
        parse_date
    )
    transformed_data = transformed_data.sort_values(by="transaction_date")

    transformed_data["ID"] = range(1, len(transformed_data) + 1)
    print(f"Total Transactions: {transformed_data}")

    # If you want to rearrange columns and put 'ID' first
    columns = ["ID"] + [col for col in transformed_data.columns if col != "ID"]
    transformed_data = transformed_data[columns]

    return transformed_data


if __name__ == "__main__":
    transformed_data = run_all_parsers()
    # You can now do something with transformed_data
    transformed_data.to_csv(OUTPUT_PATH_CSV, index=False)
    transformed_data.to_excel(OUTPUT_PATH_XLSX, index=False)
