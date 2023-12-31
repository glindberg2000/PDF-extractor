"""
PDF Data Extractor for Bank of America Statements

This script serves as a starting point for handling Bank of America's specific format.
It reads transaction data from PDF statements and exports it to Excel and CSV files.
The script scans through each page of each PDF file, extracts the relevant information,
and then sorts the transactions by date.

Usage:
    python3 -m dataextractai.parsers.bofa_visa_parser
"""

import os
import pandas as pd
import re
import PyPDF2
from PyPDF2 import PdfReader
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from ..utils.utils import standardize_column_names, get_parent_dir_and_file


SOURCE_DIR = PARSER_INPUT_DIRS["bofa_visa"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["bofa_visa"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["bofa_visa"]["xlsx"]


def append_year(row):
    """
    Append the year to the date columns in the row.

    Parameters:
        row (pd.Series): A row in the DataFrame.

    Returns:
        pd.Series: The modified row with the year appended to the date columns.
    """
    statement_date = pd.to_datetime(row["Statement Date"])
    statement_year = statement_date.year
    statement_month = statement_date.month

    for date_col in ["Transaction Date", "Posting Date"]:
        transaction_month = int(row[date_col].split("/")[0])

        # Special logic for December-January crossover
        if statement_month == 1 and transaction_month == 12:
            year_to_append = statement_year - 1
        else:
            year_to_append = statement_year

        new_date = f"{row[date_col]}/{year_to_append}"
        row[date_col] = new_date

    return row


def main(write_to_file=True):
    skipped_pages = 0
    # Initialize an empty DataFrame to store all data
    all_data = pd.DataFrame(
        columns=[
            "Transaction Date",
            "Posting Date",
            "Description",
            "Reference Number",
            "Account Number",
            "Amount",
        ]
    )

    # Loop through each PDF file in the directory
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith(".pdf"):
            statement_date = filename.split("_")[1].split(".")[0]
            print(f"processing file: {filename}")
            # Full path to the PDF file
            filepath = os.path.join(SOURCE_DIR, filename)

            # Open the PDF file
            pdfFileObj = open(filepath, "rb")

            # Initialize PDF reader object
            pdfReader = PyPDF2.PdfReader(pdfFileObj)

            # Initialize an empty list to store rows
            rows = []
            start_flag = False

            # Loop through each page in the PDF starting from page 3
            for page_num in range(2, len(pdfReader.pages)):  # Page index is 0-based
                try:
                    text = pdfReader.pages[page_num].extract_text()
                    if "Purchases and Adjustments" in text:
                        start_flag = True

                    # If in the "Purchases and Adjustments" section, start extracting rows
                    if start_flag:
                        lines = text.split("\n")
                        for line in lines:
                            match = re.match(
                                r"(\d{2}/\d{2})\s+(\d{2}/\d{2})?\s+(.*?)(\d{4})?\s+(\d{4})?\s+([\d,]+\.\d{2})?$",
                                line,
                            )
                            if match:
                                (
                                    transaction_date,
                                    posting_date,
                                    description,
                                    ref_num,
                                    acc_num,
                                    amount,
                                ) = match.groups()
                                rows.append(
                                    [
                                        transaction_date,
                                        posting_date,
                                        description,
                                        ref_num,
                                        acc_num,
                                        amount,
                                    ]
                                )
                except Exception as e:
                    skipped_pages = +1

            # Create a DataFrame from the list of rows
            df = pd.DataFrame(
                rows,
                columns=[
                    "Transaction Date",
                    "Posting Date",
                    "Description",
                    "Reference Number",
                    "Account Number",
                    "Amount",
                ],
            )
            df["Statement Date"] = statement_date
            df["File Path"] = filepath
            df = df.apply(append_year, axis=1)

            # Append this DataFrame to the all_data DataFrame
            all_data = pd.concat([all_data, df], ignore_index=True)

    # Convert the "Transaction Date" and "Posting Date" columns to datetime format
    all_data["Transaction Date"] = pd.to_datetime(
        all_data["Transaction Date"]
    ).dt.strftime("%m/%d/%Y")
    all_data["Posting Date"] = pd.to_datetime(all_data["Posting Date"]).dt.strftime(
        "%m/%d/%Y"
    )
    all_data["Statement Date"] = pd.to_datetime(all_data["Statement Date"]).dt.strftime(
        "%m/%d/%Y"
    )

    # Sort by "Transaction Date"
    all_data_sorted = all_data.sort_values(by="Transaction Date")
    print(f"Total Transactions: {len(all_data_sorted)}")

    # Standardize the Column Names
    df = standardize_column_names(all_data_sorted)
    df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)

    # Save to CSV and Excel
    if write_to_file:
        df.to_csv(OUTPUT_PATH_CSV, index=False)
        df.to_excel(OUTPUT_PATH_XLSX, index=False)

    return df


def run(write_to_file=True):
    """
    Executes the main function to process PDF files and extract data.

    Parameters:
    write_to_file (bool): A flag to determine whether the output DataFrame should be
    written to CSV and XLSX files. Defaults to True.

    Returns:
    DataFrame: A pandas DataFrame generated by the main function.
    """
    return main(write_to_file=write_to_file)


if __name__ == "__main__":
    # When running as a script, write to file by default
    run()
