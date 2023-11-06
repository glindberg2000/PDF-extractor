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


def run_all_parsers():
    print("Running all parsers...")

    # Run Amazon parser
    print("\nRunning Amazon parser...")
    run_amazon_parser()

    # Run Bank of America bank parser
    print("\nRunning Bank of America bank parser...")
    run_bofa_bank_parser()

    # Run Bank of America VISA parser
    print("\nRunning Bank of America VISA parser...")
    run_bofa_visa_parser()

    # Run Chase VISA parser
    print("\nRunning Chase VISA parser...")
    run_chase_visa_parser()

    # Run Wells Fargo bank parser
    print("\nRunning Wells Fargo bank parser...")
    run_wells_fargo_bank_parser()

    # Run Wells Fargo MasterCard parser
    print("\nRunning Wells Fargo MasterCard parser...")
    run_wells_fargo_mastercard_parser()

    print("\nAll parsers have been executed.")


if __name__ == "__main__":
    run_all_parsers()
