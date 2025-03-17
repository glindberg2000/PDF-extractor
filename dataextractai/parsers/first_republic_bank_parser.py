"""
This script processes PDF bank statements from First Republic and extracts transactions into a structured data format.
It scans the provided PDFs, identifies and parses transaction information including deposits, withdrawals, and checks,
and then exports this data to both CSV and XLSX formats for further analysis.

The script is designed to handle the First Republic Bank statement format (now part of JPMorgan Chase)
and separate different transaction types.

Author: Gregory Lindberg
Date: March 16, 2025

Usage:
      python3 -m dataextractai.parsers.firstrepublic_parser
"""

__author__ = "Gregory Lindberg"
__version__ = "1.0"
__license__ = "MIT"
__description__ = (
    "Process First Republic bank statement PDFs and extract transaction data."
)

import re
import pandas as pd
from datetime import datetime
import pdfplumber
import os
import logging
import json
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from ..utils.utils import standardize_column_names, get_parent_dir_and_file

# Set up logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SOURCE_DIR = PARSER_INPUT_DIRS["firstrepublic_bank"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["firstrepublic_bank"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["firstrepublic_bank"]["xlsx"]


def extract_statement_date(text):
    """
    Extract the statement period from the statement text.

    Parameters:
    text : str, the full text of the statement

    Returns:
    tuple: (start_date, end_date) strings in YYYY-MM-DD format
    """
    # Search for statement period pattern
    match = re.search(r"Statement Period:[\s\n]+([\w\s,]+)-[\s\n]+([\w\s,]+)", text)
    if match:
        start_date_str = match.group(1).strip()
        end_date_str = match.group(2).strip()

        # Parse and format dates
        try:
            start_date = datetime.strptime(start_date_str, "%B %d, %Y").strftime(
                "%Y-%m-%d"
            )
            end_date = datetime.strptime(end_date_str, "%B %d, %Y").strftime("%Y-%m-%d")
            logger.info(f"Found statement period: {start_date} to {end_date}")
            return (start_date, end_date)
        except ValueError:
            logger.warning(f"Could not parse dates: {start_date_str} - {end_date_str}")
            pass

    # Try numeric format
    match = re.search(
        r"Statement Period:\s+(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})", text
    )
    if match:
        start_date_str = match.group(1).strip()
        end_date_str = match.group(2).strip()

        # Parse and format dates
        try:
            start_date = datetime.strptime(start_date_str, "%m/%d/%Y").strftime(
                "%Y-%m-%d"
            )
            end_date = datetime.strptime(end_date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
            logger.info(f"Found statement period: {start_date} to {end_date}")
            return (start_date, end_date)
        except ValueError:
            logger.warning(f"Could not parse dates: {start_date_str} - {end_date_str}")
            pass

    logger.error("Could not find statement period in text")
    return (None, None)


def extract_account_number(text):
    """
    Extract the account number from the statement text.

    Parameters:
    text : str, the full text of the statement

    Returns:
    str, the account number or a masked version
    """
    match = re.search(r"Account Number:\s*(X+\d+)", text)
    if match:
        account_num = match.group(1).strip()
        logger.info(f"Found account number: {account_num}")
        return account_num

    logger.warning("Could not find account number in text")
    return None


def extract_checks(text):
    """
    Extract check information from the statement.

    Parameters:
    text : str, the statement text

    Returns:
    list, list of check transaction dictionaries
    """
    transactions = []

    # Find the Checks Paid section
    checks_section_match = re.search(
        r"Checks Paid(.*?)(?:Account Activity|Account Summary|Fee Summary|TO BALANCE)",
        text,
        re.DOTALL,
    )
    if not checks_section_match:
        logger.debug("No Checks Paid section found")
        return transactions

    checks_section = checks_section_match.group(1)
    logger.debug(f"Found Checks Paid section:\n{checks_section}")

    # Pattern to match check entries: Number, Date, Amount
    pattern = r"(\d+)\s+(\d{2}/\d{2})\s+\$([\d,]+\.\d{2})"

    matches = re.finditer(pattern, checks_section)
    for match in matches:
        check_number, date_str, amount_str = match.groups()

        # Clean amount (remove commas) and convert to float
        amount = float(amount_str.replace(",", ""))

        # Format date
        current_year = datetime.now().year
        date = f"{date_str}/{current_year}"

        transaction = {
            "transaction_date": date,
            "check_number": check_number,
            "description": f"Check #{check_number}",
            "amount": -amount,  # Negative since it's a withdrawal
            "transaction_type": "check",
        }

        logger.debug(f"Found check transaction: {transaction}")
        transactions.append(transaction)

    logger.info(f"Found {len(transactions)} check transactions")
    return transactions


def extract_deposits_credits(text):
    """
    Extract deposit and credit transactions from the statement.

    Parameters:
    text : str, the statement text

    Returns:
    list, list of deposit transaction dictionaries
    """
    transactions = []

    # First find the "Deposits and Credits" section within "Account Activity"
    deposits_section_match = re.search(
        r"Deposits and Credits(.*?)(?:Withdrawals and Debits|Total Deposits and Credits)",
        text,
        re.DOTALL,
    )
    if not deposits_section_match:
        logger.debug("No Deposits and Credits section found")
        return transactions

    deposits_section = deposits_section_match.group(1)
    logger.debug(f"Found Deposits and Credits section:\n{deposits_section}")

    # Pattern to match deposit entries: Date, Description, Amount
    pattern = r"(\d{2}/\d{2})\s+(.*?)(?=\$)([\d,]+\.\d{2})"

    matches = re.finditer(pattern, deposits_section)
    for match in matches:
        date_str, description, amount_str = match.groups()

        # Clean amount (remove commas) and convert to float
        amount = float(amount_str.replace(",", ""))

        # Format date
        current_year = datetime.now().year
        date = f"{date_str}/{current_year}"

        transaction = {
            "transaction_date": date,
            "description": description.strip(),
            "amount": amount,  # Positive since it's a deposit
            "transaction_type": "deposit",
        }

        logger.debug(f"Found deposit transaction: {transaction}")
        transactions.append(transaction)

    logger.info(f"Found {len(transactions)} deposit transactions")
    return transactions


def extract_withdrawals_debits(text):
    """
    Extract withdrawal and debit transactions from the statement.

    Parameters:
    text : str, the statement text

    Returns:
    list, list of withdrawal transaction dictionaries
    """
    transactions = []

    # Find the "Withdrawals and Debits" section within "Account Activity"
    withdrawals_section_match = re.search(
        r"Withdrawals and Debits(.*?)(?:Total Withdrawals and Debits|ANNUAL PERCENTAGE)",
        text,
        re.DOTALL,
    )
    if not withdrawals_section_match:
        logger.debug("No Withdrawals and Debits section found")
        return transactions

    withdrawals_section = withdrawals_section_match.group(1)
    logger.debug(f"Found Withdrawals and Debits section:\n{withdrawals_section}")

    # Pattern to match withdrawal entries: Date, Description, Amount
    pattern = r"(\d{2}/\d{2})\s+(.*?)(?=\$)([\d,]+\.\d{2})\s*-"

    matches = re.finditer(pattern, withdrawals_section)
    for match in matches:
        date_str, description, amount_str = match.groups()

        # Clean amount (remove commas) and convert to float
        amount = float(amount_str.replace(",", ""))

        # Format date
        current_year = datetime.now().year
        date = f"{date_str}/{current_year}"

        transaction = {
            "transaction_date": date,
            "description": description.strip(),
            "amount": -amount,  # Negative since it's a withdrawal
            "transaction_type": "withdrawal",
        }

        logger.debug(f"Found withdrawal transaction: {transaction}")
        transactions.append(transaction)

    logger.info(f"Found {len(transactions)} withdrawal transactions")
    return transactions


def extract_all_transactions(
    text, statement_start_date, statement_end_date, account_number, pdf_path
):
    """
    Extract all types of transactions from the statement text.

    Parameters:
    text : str, the full text of the statement
    statement_start_date : str, the start date of the statement period
    statement_end_date : str, the end date of the statement period
    account_number : str, the account number
    pdf_path : str, the path to the PDF file

    Returns:
    list, list of all transaction dictionaries
    """
    all_transactions = []

    # Extract different transaction types
    checks = extract_checks(text)
    deposits = extract_deposits_credits(text)
    withdrawals = extract_withdrawals_debits(text)

    # Combine all transactions
    all_transactions.extend(checks)
    all_transactions.extend(deposits)
    all_transactions.extend(withdrawals)

    # Add statement information to each transaction
    for transaction in all_transactions:
        transaction["statement_start_date"] = statement_start_date
        transaction["statement_end_date"] = statement_end_date
        transaction["account_number"] = account_number
        transaction["file_path"] = pdf_path

    return all_transactions


def update_transaction_years(transactions, statement_end_date):
    """
    Update transaction years based on statement date to handle month transitions.

    Parameters:
    transactions : list, list of transaction dictionaries
    statement_end_date : str, the end date of the statement period

    Returns:
    list, updated transaction dictionaries
    """
    if not statement_end_date:
        return transactions

    try:
        statement_date = datetime.strptime(statement_end_date, "%Y-%m-%d")
        statement_year = statement_date.year
        statement_month = statement_date.month

        for transaction in transactions:
            # Skip if missing transaction_date
            if "transaction_date" not in transaction:
                continue

            try:
                # Parse the transaction date
                trans_date = datetime.strptime(
                    transaction["transaction_date"], "%m/%d/%Y"
                )

                # If statement is in January and transaction is in December, use previous year
                if statement_month == 1 and trans_date.month == 12:
                    trans_date = trans_date.replace(year=statement_year - 1)
                else:
                    trans_date = trans_date.replace(year=statement_year)

                # Update the transaction date
                transaction["transaction_date"] = trans_date.strftime("%Y-%m-%d")
                logger.debug(
                    f"Updated transaction date: {transaction['transaction_date']}"
                )
            except ValueError as e:
                logger.warning(
                    f"Could not process date {transaction['transaction_date']}: {e}"
                )

    except ValueError as e:
        logger.error(f"Could not process statement date {statement_end_date}: {e}")

    return transactions


def process_pdf(pdf_path):
    """
    Process a single PDF file and extract transactions.

    Parameters:
    pdf_path : str, path to the PDF file

    Returns:
    list, a list of transaction dictionaries
    """
    transactions = []
    logger.info(f"Processing file: {pdf_path}")

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages and combine
            full_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                logger.debug(f"Extracted text from page:\n{page_text}")
                full_text += page_text + "\n"

            # Extract statement information
            statement_start_date, statement_end_date = extract_statement_date(full_text)
            account_number = extract_account_number(full_text)

            if not statement_start_date or not statement_end_date:
                logger.error("Could not extract statement dates")
                return []

            if not account_number:
                logger.warning("Could not extract account number")

            # Extract different types of transactions
            checks = extract_checks(full_text)
            deposits = extract_deposits_credits(full_text)
            withdrawals = extract_withdrawals_debits(full_text)

            # Combine all transactions
            all_transactions = []
            all_transactions.extend(checks)
            all_transactions.extend(deposits)
            all_transactions.extend(withdrawals)

            # Add statement information to each transaction
            for transaction in all_transactions:
                transaction["statement_start_date"] = statement_start_date
                transaction["statement_end_date"] = statement_end_date
                transaction["account_number"] = account_number
                transaction["file_path"] = pdf_path

            transactions = update_transaction_years(
                all_transactions, statement_end_date
            )

    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {e}")

    logger.info(f"Found total of {len(transactions)} transactions")
    return transactions


def process_all_pdfs(source_dir):
    """
    Process all PDFs in the source directory.

    Parameters:
    source_dir : str, the directory containing PDF files

    Returns:
    list, a list of all transactions from all PDFs
    """
    all_transactions = []

    for filename in os.listdir(source_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(source_dir, filename)
            logger.info(f"Processing file: {filename}")

            transactions = process_pdf(pdf_path)
            all_transactions.extend(transactions)

    return all_transactions


def main(write_to_file=True):
    """
    Main function to process PDFs and save results.

    Parameters:
    write_to_file : bool, whether to write results to file

    Returns:
    DataFrame, the processed transaction data
    """
    # Process all PDFs in the source directory
    all_transactions = process_all_pdfs(SOURCE_DIR)

    logger.info(f"Total Transactions: {len(all_transactions)}")

    if not all_transactions:
        logger.warning("No transactions found!")
        return pd.DataFrame()

    # Convert to DataFrame
    df = pd.DataFrame(all_transactions)

    # Standardize column names
    df = standardize_column_names(df)

    # Format file path
    if "file_path" in df.columns:
        df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)

    # Save to CSV and Excel
    if write_to_file and not df.empty:
        df.to_csv(OUTPUT_PATH_CSV, index=False)
        df.to_excel(OUTPUT_PATH_XLSX, index=False)
        logger.info(f"Saved {len(df)} transactions to CSV and Excel files")

    return df


def run(write_to_file=True):
    """
    Run the parser.

    Parameters:
    write_to_file : bool, whether to write results to file

    Returns:
    DataFrame, the processed transaction data
    """
    return main(write_to_file=write_to_file)


if __name__ == "__main__":
    # When running as a script, write to file by default
    run()
