"""
PDF Data Extractor for Bank of America Bank Statements

This script serves as a starting point for handling Bank of America's bank format.
It reads transaction data from PDF statements and exports it to Excel and CSV files and returns a dataframe.
The script scans through each page of each PDF file, extracts the relevant information,
and then sorts the transactions by date.

Usage:
    python3 -m dataextractai.parsers.bofa_bank_parser
"""

import pdfplumber
import pandas as pd
import re
import os
import glob
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from ..utils.utils import standardize_column_names, get_parent_dir_and_file
from PyPDF2 import PdfReader
import logging

SOURCE_DIR = PARSER_INPUT_DIRS["bofa_bank"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["bofa_bank"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["bofa_bank"]["xlsx"]

logger = logging.getLogger("bofa_bank_parser")


def add_statement_date_and_file_path(df, file_path):
    """
    Enhance a DataFrame with the statement date and file path information.

    Statement date extraction prioritizes PDF content (statement period or explicit date fields). Only falls back to filename if content-based extraction fails. If both fail, logs a warning and sets statement_date to None.
    """
    statement_date = None
    try:
        reader = PdfReader(file_path)
        first_page_text = reader.pages[0].extract_text() if reader.pages else ""
        match = re.search(
            r"Statement Period\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})",
            first_page_text,
        )
        if match:
            period_end = match.group(2)
            try:
                statement_date = pd.to_datetime(period_end, format="%m/%d/%Y").date()
            except Exception:
                pass
        if not statement_date:
            base_name = os.path.basename(file_path).split(".")[0]
            parts = base_name.split("_")
            if len(parts) == 2:
                _, date_str = parts
                try:
                    statement_date = pd.to_datetime(date_str).date()
                    logger.warning(
                        f"Statement date not found in content, using filename: {statement_date}"
                    )
                except Exception:
                    statement_date = None
            if not statement_date:
                logger.warning(
                    "Could not extract statement date from content or filename. Setting to None."
                )
    except Exception:
        logger.warning(
            "Could not extract statement date from content or filename. Setting to None."
        )
        statement_date = None

    df["Statement Date"] = statement_date
    df["File Path"] = file_path
    return df


def clean_amount(amount_string):
    # Remove commas and convert to float
    return float(amount_string.replace(",", "").replace("$", ""))


def parse_transactions(text_list):
    date_pattern = r"\d{2}/\d{2}/\d{2}"
    amount_pattern = r"[-]?\d+,\d+\.\d+|[-]?\d+\.\d+"
    deposits_additions = []
    withdrawals_subtractions = []
    checks = []
    in_deposits_section = False
    in_withdrawals_section = False
    in_checks_section = False
    for page_text in text_list:
        lines = page_text.split("\n")
        for line in lines:
            if "Deposits and other additions" in line:
                in_deposits_section = True
                in_withdrawals_section = False
                in_checks_section = False
                continue
            elif "Withdrawals and other subtractions" in line:
                in_deposits_section = False
                in_withdrawals_section = True
                in_checks_section = False
                continue
            elif "Checks" in line:
                in_deposits_section = False
                in_withdrawals_section = False
                in_checks_section = True
                continue
            if in_deposits_section or in_withdrawals_section:
                date_match = re.search(date_pattern, line)
                amount_match = re.search(amount_pattern, line)
                if date_match and amount_match:
                    date = date_match.group()
                    amount = clean_amount(amount_match.group())
                    description = line[date_match.end() : amount_match.start()].strip()
                    if in_deposits_section:
                        deposits_additions.append((date, description, amount))
                    elif in_withdrawals_section:
                        withdrawals_subtractions.append((date, description, amount))
            elif in_checks_section:
                # Define patterns
                date_pattern = r"\b(\d{2}/\d{2}/\d{2})\b"  # Match dates with boundaries to ensure separation
                check_num_pattern = (
                    r"\b(\d{2}/\d{2}/\d{2})\s+(\d+)\b"  # Match check number after date
                )
                amount_pattern = r"(-?\d{1,3}(?:,\d{3})*(?:\.\d{2}))"  # Match amounts in the correct format

                # Search for patterns in the line
                date_match = re.search(date_pattern, line)
                check_num_match = re.search(check_num_pattern, line)
                amount_match = re.search(amount_pattern, line)

                if date_match and check_num_match and amount_match:
                    # Extract the date and check number
                    date = date_match.group(1)
                    check_num = check_num_match.group(
                        2
                    )  # Group 2 is the check number following the date
                    # Format the check number output
                    check_output = f"Check No {check_num}: Rent Payment"
                    # print(f"Date: {date}, {check_output}, Line: {line}")

                    # Extract and clean the amount
                    amount = clean_amount(
                        amount_match.group(1)
                    )  # Group 1 is the entire matched amount
                    # print(f"Amount: {amount}")

                    # Append the extracted data to the checks list
                    checks.append((date, check_output, amount))

    deposits_df = pd.DataFrame(
        deposits_additions, columns=["Date", "Description", "Amount"]
    )
    withdrawals_df = pd.DataFrame(
        withdrawals_subtractions, columns=["Date", "Description", "Amount"]
    )
    checks_df = pd.DataFrame(checks, columns=["Date", "Check Number", "Amount"])
    # Add a 'Transaction Type' column to each DataFrame
    deposits_df["Transaction Type"] = "Deposit"
    withdrawals_df["Transaction Type"] = "Withdrawal"
    checks_df["Transaction Type"] = "Withdrawal"

    # Rename 'Check Number' column in checks_df to match the 'Description' column in the other DataFrames
    checks_df.rename(columns={"Check Number": "Description"}, inplace=True)

    # Drop empty or all-NA columns for each DataFrame before concatenation
    deposits_df = deposits_df.dropna(axis=1, how="all")
    withdrawals_df = withdrawals_df.dropna(axis=1, how="all")
    checks_df = checks_df.dropna(axis=1, how="all")

    # Concatenate the DataFrames into a single DataFrame
    combined_df = pd.concat([deposits_df, withdrawals_df, checks_df], ignore_index=True)
    # If 'date' is the column with the Bank of America VISA dates
    # combined_df["date"] = pd.to_datetime(combined_df["date"]).dt.strftime("%m/%d/%Y")

    return combined_df


def extract_text_from_pdf(pdf_path):
    all_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= 2:
                text = page.extract_text()
                all_text.append(text)
    return all_text


def get_page_count(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages)


def extract_text_by_page(pdf_path, page_number):
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number]
        return page.extract_text()


def check_encryption(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        # Check if the metadata can be accessed as a proxy for encryption
        try:
            metadata = pdf.metadata
            return {"encrypted": False, "metadata": metadata}
        except:
            return {"encrypted": True, "metadata": None}


def main(write_to_file=True):
    all_transactions = []
    for file_path in glob.glob(os.path.join(SOURCE_DIR, "*.pdf")):
        text_list = extract_text_from_pdf(file_path)
        transactions_df = parse_transactions(text_list)
        print(f"Processing File: {file_path}")
        transactions_df = add_statement_date_and_file_path(transactions_df, file_path)

        # Drop columns that are entirely NA (if not needed)
        transactions_df = transactions_df.dropna(axis=1, how="all")

        all_transactions.append(transactions_df)

    # Concatenate all transactions into a single DataFrame
    combined_transactions_df = pd.concat(all_transactions, ignore_index=True)
    print(f"Total Transactions: {len(combined_transactions_df)}")

    # Standardize the Column Names
    df = standardize_column_names(combined_transactions_df)
    df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)

    # Convert to datetime with two-digit year
    df["date"] = pd.to_datetime(df["date"], format="%m/%d/%y")

    # Format datetime as string with four-digit year
    df["date"] = df["date"].dt.strftime("%m/%d/%Y")

    # Normalie the amount so it matches our other statement export: payments + and deposits -

    df["amount"] = df["amount"] * -1

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
