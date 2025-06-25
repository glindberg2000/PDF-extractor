"""
This script processes PDF Mastercard statements from Wells Fargo and extracts transactions into a structured data format. It scans the provided PDFs, identifies and parses transaction information, and then exports this data to both CSV and XLSX formats for further analysis.

The script is designed to handle multiple types of transaction entries, including those that span multiple lines, and to differentiate between deposits and withdrawals based on keyword search.

Author: Gregory Lindberg
Date: November 4, 2023

Usage:
      python3 -m dataextractai.parsers.wellsfargo_mastercard_parser
"""

__author__ = "Gregory Lindberg"
__version__ = "1.0"
__license__ = "MIT"
__description__ = (
    "Process Wells Fargo Mastercard statement PDFs and extract transaction data."
)

import re
import pandas as pd
from datetime import datetime
import pdfplumber
import os
import pprint
import json
import csv
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from ..utils.utils import standardize_column_names, get_parent_dir_and_file
from PyPDF2 import PdfReader
import logging
from typing import List, Dict, Any
from ..parsers_core.base import BaseParser
from ..parsers_core.registry import ParserRegistry
from ..parsers_core.models import ParserOutput, TransactionRecord, StatementMetadata

SOURCE_DIR = PARSER_INPUT_DIRS["wellsfargo_mastercard"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["wellsfargo_mastercard"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["wellsfargo_mastercard"]["xlsx"]
FILTERED_PATH_CSV = PARSER_OUTPUT_PATHS["wellsfargo_mastercard"]["filtered"]

logger = logging.getLogger("wellsfargo_mastercard_parser")


class WellsFargoMastercardParser(BaseParser):
    """
    Modular parser for Wells Fargo Mastercard PDF statements.
    """

    def can_parse(self, file_path: str) -> bool:
        print(f"[DEBUG] can_parse called with file_path: {file_path}")
        try:
            reader = PdfReader(file_path)
            text = ""
            for page in reader.pages[:2]:
                text += page.extract_text() or ""
            text = text.lower()
            result = (
                "wells fargo" in text
                and "account number" in text
                and ("business card" in text or "credit line" in text)
            )
            print(f"[DEBUG] can_parse result for {file_path}: {result}")
            return result
        except Exception as e:
            print(f"[DEBUG] can_parse error for {file_path}: {e}")
            return False

    def parse_file(self, input_path: str, config: Dict[str, Any] = None) -> List[Dict]:
        pdf_reader = PdfReader(input_path)
        text = "\n".join([page.extract_text() or "" for page in pdf_reader.pages])
        raw_transactions = self._parse_transactions(text)
        # Attach file path for metadata extraction
        for t in raw_transactions:
            t["file_path"] = input_path
        return raw_transactions

    def normalize_data(self, raw_data: List[Dict], file_path: str = None) -> List[Dict]:
        if not raw_data:
            return []
        df = pd.DataFrame(raw_data)
        # Ensure required columns exist
        if "file_path" not in df.columns:
            df["file_path"] = file_path or ""
        df = handle_credits_charges(df)
        normalized = []
        for _, row in df.iterrows():
            # Date normalization
            date_str = row.get("transaction_date")
            if date_str and isinstance(date_str, datetime):
                date_str = date_str.strftime("%Y-%m-%d")
            elif date_str and re.match(r"\d{2}/\d{2}/\d{4}", str(date_str)):
                date_str = datetime.strptime(date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
            elif date_str and re.match(r"\d{2}/\d{2}/\d{2}", str(date_str)):
                date_str = datetime.strptime(date_str, "%m/%d/%y").strftime("%Y-%m-%d")
            # Description
            description = row.get("description") or row.get("transaction_text") or ""
            # Posted date
            posted_date = row.get("post_date")
            if posted_date and isinstance(posted_date, datetime):
                posted_date = posted_date.strftime("%Y-%m-%d")
            # Build TransactionRecord
            normalized.append(
                {
                    "transaction_date": date_str,
                    "amount": row.get("amount"),
                    "description": description,
                    "posted_date": posted_date,
                    "transaction_type": row.get("classification")
                    or row.get("transaction_type"),
                    "credits": row.get("credits", 0.0),
                    "charges": row.get("charges", 0.0),
                    "extra": {
                        k: v
                        for k, v in row.items()
                        if k
                        not in [
                            "transaction_date",
                            "amount",
                            "charges",
                            "credits",
                            "description",
                            "transaction_text",
                            "post_date",
                            "transaction_type",
                            "classification",
                        ]
                    },
                }
            )
        return normalized

    def extract_metadata(
        self, raw_data: List[Dict], input_path: str
    ) -> StatementMetadata:
        # Extract statement dates from PDF content
        statement_date = None
        statement_period_start = None
        statement_period_end = None
        statement_date_source = None
        try:
            reader = PdfReader(input_path)
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
            # Try to find 'Statement Period MM/DD/YY to MM/DD/YY'
            match_period = re.search(
                r"Statement Period\s+(\d{2}/\d{2}/\d{2,4})\s+to\s+(\d{2}/\d{2}/\d{2,4})",
                text,
            )
            if match_period:
                statement_period_start = match_period.group(1)
                statement_period_end = match_period.group(2)
                # Format as YYYY-MM-DD
                for var, val in [
                    ("statement_period_start", statement_period_start),
                    ("statement_period_end", statement_period_end),
                ]:
                    if val:
                        try:
                            if len(val.split("/")) == 3:
                                m, d, y = val.split("/")
                                y = int(y)
                                if y < 100:
                                    y += 2000
                                val_fmt = f"{y:04d}-{int(m):02d}-{int(d):02d}"
                                if var == "statement_period_start":
                                    statement_period_start = val_fmt
                                else:
                                    statement_period_end = val_fmt
                        except Exception:
                            pass
                statement_date_source = "content"
            # Try to find 'Statement Closing Date MM/DD/YY'
            match_close = re.search(
                r"Statement Closing Date\s+(\d{2}/\d{2}/\d{2,4})", text
            )
            if match_close:
                val = match_close.group(1)
                try:
                    if len(val.split("/")) == 3:
                        m, d, y = val.split("/")
                        y = int(y)
                        if y < 100:
                            y += 2000
                        statement_date = f"{y:04d}-{int(m):02d}-{int(d):02d}"
                        statement_date_source = "content"
                except Exception:
                    pass
            # Fallback: if no closing date, use period end
            if not statement_date and statement_period_end:
                statement_date = statement_period_end
                statement_date_source = "period_end"
        except Exception:
            pass
        # Fallback: try to infer from filename
        if not statement_date:
            base_name = os.path.basename(input_path).split(".")[0].strip()
            date_str = base_name[:6]
            try:
                statement_date = datetime.strptime(date_str, "%m%d%y").strftime(
                    "%Y-%m-%d"
                )
                statement_date_source = "filename"
            except Exception:
                statement_date = None
                statement_date_source = None
        # Account number extraction (as before)
        account_number = None
        try:
            reader = PdfReader(input_path)
            for page in reader.pages:
                text = page.extract_text() or ""
                match = re.search(r"Account Number:?\s*([\d\s]+)", text)
                if match:
                    account_number = match.group(1).replace(" ", "").strip()
                    break
        except Exception:
            pass
        return StatementMetadata(
            statement_date=statement_date,
            statement_period_start=statement_period_start,
            statement_period_end=statement_period_end,
            statement_date_source=statement_date_source,
            original_filename=os.path.basename(input_path),
            account_number=account_number,
            bank_name="Wells Fargo",
            account_type="mastercard",
            parser_name="wellsfargo_mastercard_parser",
        )

    def _parse_transactions(self, text: str) -> List[Dict]:
        # New logic: match lines like 01/1201/12F1821000C00CHGDDA AUTOMATIC PAYMENT - THANK YOU 46.00
        transactions = []
        # Only look for transactions after the header
        in_transactions = False
        for line in text.split("\n"):
            line = line.strip()
            if not in_transactions:
                if line.startswith(
                    "TransPostReference Number Description Credits Charges"
                ):
                    in_transactions = True
                continue
            # Regex for transaction lines
            m = re.match(
                r"(\d{2}/\d{2})(\d{2}/\d{2})([A-Z0-9]+)\s+(.+?)\s+(\d+\.\d{2})$", line
            )
            if m:
                trans_date, post_date, ref_num, desc, amount = m.groups()
                # Use statement year for full date
                year = datetime.now().year
                # Try to infer year from statement metadata if available
                try:
                    # If statement date is in the file, use that year
                    year_match = re.search(
                        r"Statement Closing Date (\d{2}/\d{2}/(\d{2,4}))", text
                    )
                    if year_match:
                        year_str = year_match.group(1)
                        if len(year_str.split("/")) == 3:
                            year = int(year_str.split("/")[-1])
                        elif len(year_str.split("/")) == 2:
                            year = 2000 + int(year_str.split("/")[-1])
                except Exception:
                    pass
                # Format dates
                trans_date_full = (
                    f"{year}-{int(trans_date[:2]):02d}-{int(trans_date[3:]):02d}"
                )
                post_date_full = (
                    f"{year}-{int(post_date[:2]):02d}-{int(post_date[3:]):02d}"
                )
                # Classification
                classification = (
                    "credit"
                    if ("AUTOMATIC PAYMENT" in desc or "ONLINE PAYMENT" in desc)
                    else "charge"
                )
                transactions.append(
                    {
                        "transaction_date": trans_date_full,
                        "post_date": post_date_full,
                        "reference_number": ref_num,
                        "description": desc,
                        "amount": float(amount),
                        "classification": classification,
                    }
                )
        return transactions

    def _process_transaction_block(self, lines: List[str]) -> Dict:
        # No longer used with new _parse_transactions logic, but kept for compatibility
        return {}


# Register the parser
ParserRegistry.register_parser(
    name="wellsfargo_mastercard", parser_cls=WellsFargoMastercardParser
)


def analyze_line_for_transaction_type_all(line):
    """
    Analyze a line of text and determine the transaction type based on keyword search.

    Parameters:
    line : str, the line of text to analyze

    Returns:
    str, the determined transaction type ('deposit', 'withdrawal', or 'unknown')
    """
    result = {}

    if "AUTOMATIC PAYMENT" in line or "ONLINE PAYMENT" in line:
        result["classification"] = "credit"
    else:
        result["classification"] = "charge"
    return result


def add_statement_date_and_file_path(transaction, pdf_path):
    """
    Enhance a transaction dictionary with the statement date and file path information.

    Statement date extraction prioritizes PDF content (statement period or explicit date fields). Only falls back to filename if content-based extraction fails. If both fail, logs a warning and sets statement_date to None.
    """
    # Try to extract statement date from PDF content
    try:
        reader = PdfReader(pdf_path)
        first_page_text = reader.pages[0].extract_text() if reader.pages else ""
        match = re.search(
            r"Statement Period\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})",
            first_page_text,
        )
        statement_date = None
        if match:
            period_end = match.group(2)
            try:
                statement_date = datetime.strptime(period_end, "%m/%d/%Y").strftime(
                    "%Y-%m-%d"
                )
            except Exception:
                pass
        if not statement_date:
            base_name = os.path.basename(pdf_path).split(".")[0]
            date_str = base_name[:6]
            try:
                statement_date = datetime.strptime(date_str, "%m%d%y").strftime(
                    "%Y-%m-%d"
                )
                logger.warning(
                    f"Statement date not found in content, using filename: {statement_date}"
                )
            except Exception:
                logger.warning(
                    "Could not extract statement date from content or filename. Setting to None."
                )
                statement_date = None
    except Exception:
        logger.warning(
            "Could not extract statement date from content or filename. Setting to None."
        )
        statement_date = None

    transaction["statement_date"] = statement_date
    transaction["file_path"] = pdf_path
    if isinstance(transaction.get("transaction_date"), datetime):
        transaction["transaction_date"] = transaction["transaction_date"].date()
    return transaction


def parse_transactions(text):
    """
    Parse the provided text from a mastercard statement and extract transactions.

    This function splits the input text into lines and uses a regular expression to identify the start of a transaction by a date pattern. Each transaction is gathered into a block, which is then processed to extract detailed transaction data.

    Parameters
    ----------
    text : str
        The complete text from a bank statement where transactions are separated by newline characters.

    Returns
    -------
    list of dicts
        A list of dictionaries, each representing a transaction with its extracted data.

    Examples
    --------
    >>> text = "1/4 1/4 RefNo111111 Grocery Store 50.00\n1/5 Online Payment Received 100.00\nPERIODIC*FINANCE"
    >>> parse_transactions(text)
    [    {
        'transaction_date': '2023-01-04',
        'post_date': '2023-01-04',
        'reference_number': 'REF123455',
        'credits': 0,
        'charges': 200.00,
        'statement_date': '2023-01-04',
        'file_path' '/path/to/statement010423.pdf'
    }]
    """

    lines = text.split("\n")
    transactions = []
    current_transaction = []
    date_pattern = re.compile(
        r"^\s*\d{1,2}/\d{1,2}\s+\d{1,2}/\d{1,2}"  # Matches two dates at the start of the line
    )
    # Matches a date at the start of the line
    for line in lines:
        if date_pattern.match(line) or "PERIODIC*FINANCE" in line:
            if current_transaction:  # If we've gathered a transaction, process it
                transactions.append(process_transaction_block(current_transaction))
                current_transaction = []  # Reset for the next transaction
            if "PERIODIC*FINANCE" not in line:  # Ignore the "PERIODIC*FINANCE" line
                current_transaction.append(line)
        elif current_transaction:  # If we're currently gathering a transaction
            current_transaction.append(line)

    return transactions


def process_transaction_block(lines):
    """
    Process a block of text representing a single transaction and structure the data.

    This function joins a list of lines representing a transaction into a single string and analyzes it to identify
    monetary values and classify the transaction type. It then extracts the date, description, and amounts for deposits
    or withdrawals, and formats this information into a dictionary. If a transaction spans multiple lines, it is
    handled accordingly. The balance is extracted if present.

    Parameters
    ----------
    lines : list of str
        The list of lines from a bank statement that together represent a single transaction.

    Returns
    -------
    dict
        A dictionary with structured transaction data, including date, description, deposits, withdrawals,
        and ending daily balance.

    Examples
    --------
    >>> lines = ["1/4 Some Description - 50.00", " Ending Daily Balance 1,500.00"]
    >>> process_transaction_block(lines)
    {
        'transaction_date': '2023-01-04',
        'post_date': '2023-01-04',
        'reference_number': 'REF123455',
        'credits': 0,
        'charges': 200.00,
        'statement_date': '2023-01-04',
        'file_path' '/path/to/statement010423.pdf'
    }
    """

    transaction_text = " ".join(lines)
    transaction_analysis = analyze_line_for_transaction_type_all(transaction_text)
    monetary_values = re.findall(r"-?\d{1,3}(?:,\d{3})*\.\d{2}", transaction_text)

    if not monetary_values:
        # Handle error: no monetary values found
        return {}

    # Assume the last one monetary patterns are withdrawals/deposits and balance
    transaction_amount = monetary_values[-1]
    # Remove the last monetary value (the transaction amount) from the text
    transaction_text = transaction_text.rsplit(transaction_amount, 1)[0]

    mastercard_transaction_pattern = re.compile(
        r"(\d{2}/\d{2})\s+"  # First Date (MM/DD)
        r"(\d{2}/\d{2})\s+"  # Second Date (MM/DD)
        r"([\d\w]+)\s+"  # Reference Number (alphanumeric with no spaces)
        r"(.+)"  # Description (alphanumeric with spaces, potentially including numbers)
    )

    match = mastercard_transaction_pattern.search(transaction_text)
    if match:
        # Extract the two dates, reference number, and description
        first_date_str, second_date_str, reference, description = match.groups()

        # Process dates
        transaction_date = (
            datetime.strptime(first_date_str, "%m/%d")
            .date()
            .replace(year=datetime.now().year)
        )
        post_date = (
            datetime.strptime(second_date_str, "%m/%d")
            .date()
            .replace(year=datetime.now().year)
        )

        # Remove the reference number and dates from the transaction text to leave only the description
        description_text = re.sub(
            r"^\s*\d{2}/\d{2}\s+\d{2}/\d{2}\s+[\d\w]+\s+", "", transaction_text
        ).strip()

        # Classify the transaction as deposit or withdrawal
        if transaction_analysis["classification"] == "credit":
            credits = transaction_amount
            charges = "0.00"
        elif transaction_analysis["classification"] == "charge":
            charges = transaction_amount
            credits = "0.00"
        else:
            charges = transaction_amount
            credits = "0.00"

        # Construct the transaction dictionary
        transaction_dict = {
            "transaction_date": transaction_date,
            "post_date": post_date,
            "reference_number": reference,
            "description": description_text,
            "credits": credits,
            "charges": charges,
        }
        return transaction_dict
    else:
        # Handle error: no match found, which means the line didn't have the expected format
        return {}

    return transaction_dict


def extract_transactions_from_page(pdf_path):
    """
    Open a PDF bank statement, extract transactions from the second page, and return them in JSON format.

    The function uses the PyMuPDF library to open a PDF document and extract the text from its second page. It then
    parses the text to identify and structure transaction data, which is subsequently converted into a JSON string
    using Python's built-in json module.

    Parameters
    ----------
    pdf_path : str
        The file path to the PDF bank statement.

    Returns
    -------
    str
        A JSON string representing the list of structured transactions extracted from the page.

    Examples
    --------
    >>> pdf_path = '/path/to/mastercard_statement.pdf'
    >>> json_data = extract_transactions_from_page(pdf_path)
    >>> print(json_data)
    "[{
        'transaction_date': '2023-01-04',
        'post_date': '2023-01-04',
        'reference_number': 'REF123455',
        'credits': 0,
        'charges': 200.00,
        'statement_date': '2023-01-04',
        'file_path' '/path/to/statement010423.pdf'
    }]"
    """

    # Open the PDF file
    with pdfplumber.open(pdf_path) as pdf:
        print(f"processing file: {pdf_path}")
        # Extract the text of the third page
        page_text = pdf.pages[2].extract_text()  # pages[2] is the third page

    # Split the text into lines
    lines = page_text.split("\n")

    # Parse Transactions
    structured_transactions = parse_transactions(page_text)

    # Convert to JSON
    json_data = json.dumps(structured_transactions, default=str, indent=4)
    return json_data


def update_transaction_years(transactions):
    """
    Update the years of the transaction and post dates based on the statement date within each transaction.
    If the statement date is in January and the transaction or post date is in December,
    the year of the transaction or post date is set to the previous year. Otherwise, the year
    is set to the year of the statement date.

    Parameters
    ----------
    transactions : list of dict
        List of transaction dictionaries to be updated.

    Returns
    -------
    list of dict
        The list of updated transaction dictionaries with corrected years in dates.
    """
    # Process each transaction to update the years
    for transaction in transactions:
        # Extract the year from the statement date within the transaction
        statement_date = datetime.strptime(
            transaction["statement_date"], "%Y-%m-%d"
        ).date()
        statement_year = statement_date.year

        # Update transaction_date and post_date
        for date_key in ["transaction_date", "post_date"]:
            if date_key in transaction:
                # Parse the existing date
                existing_date = datetime.strptime(
                    transaction[date_key], "%Y-%m-%d"
                ).date()
                # If the month is January and the existing date is December, subtract a year
                if statement_date.month == 1 and existing_date.month == 12:
                    transaction[date_key] = existing_date.replace(
                        year=statement_year - 1
                    ).strftime("%Y-%m-%d")
                else:
                    transaction[date_key] = existing_date.replace(
                        year=statement_year
                    ).strftime("%Y-%m-%d")

    return transactions


def process_all_pdfs(source_dir):
    """
    Iterate through a directory of PDF bank statements, extract transactions, and compile them.

    This function scans a specified directory for PDF files, processes each file to extract transaction data,
    and appends each transaction to a master list. It also enhances each transaction with the statement date and
    file path using the 'add_statement_date_and_file_path' function.

    Parameters
    ----------
    source_dir : str
        The directory path where PDF bank statements are stored.

    Returns
    -------
    list of dict
        A list of transaction dictionaries with the following structure:
        [
            {
                'transaction_date': 'YYYY-MM-DD',  # The date of the transaction.
                'post_date': 'YYYY-MM-DD',         # The date the transaction was posted.
                'reference_number': str,           # A unique alphanumeric identifier for the transaction.
                'credits': float,                  # The credit amount in the transaction, 0 if none.
                'charges': float,                  # The charge amount in the transaction, 0 if none.
                'statement_date': 'YYYY-MM-DD',    # The date of the bank statement.
                'file_path': str                   # The path to the original PDF file.
            },
            ...  # Additional transaction dictionaries.
        ]

    Each transaction dictionary contains detailed information about a single transaction extracted from a bank statement PDF.
    The 'transaction_date' and 'post_date' are formatted as ISO-8601 standard dates.
    The 'credits' and 'charges' fields represent monetary values and are set to 0 if they do not apply to the transaction.
    The 'statement_date' is extracted from the filename of the PDF and is assumed to be the issue date of the bank statement.
    The 'file_path' is the absolute path to the PDF file from which the transaction was extracted.
    """
    all_transactions = []
    for filename in os.listdir(source_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(source_dir, filename)
            transactions_json = extract_transactions_from_page(pdf_path)
            transactions_data = json.loads(transactions_json)
            # Add additional data like statement date
        for transaction in transactions_data:
            updated_transaction = add_statement_date_and_file_path(
                transaction, pdf_path
            )
            all_transactions.append(updated_transaction)

    all_transactions = update_transaction_years(all_transactions)

    return all_transactions


def handle_credits_charges(df):
    # Ensure 'credits' and 'charges' columns exist
    if "credits" not in df.columns:
        df["credits"] = 0.0
    if "charges" not in df.columns:
        df["charges"] = 0.0
    # Now safely process
    df["credits"] = df["credits"].replace("[\$,]", "", regex=True).astype(float)
    df["charges"] = df["charges"].replace("[\$,]", "", regex=True).astype(float)
    df["amount"] = df["charges"] - df["credits"]
    return df


def main(write_to_file=True):
    """Process all PDF bank statements and export transactions to CSV and Excel.

    Parameters:
    source_dir (str): The directory where PDF bank statements are located.
    csv_output_path (str): The file path for the output CSV file.
    xlsx_output_path (str): The file path for the output Excel file.
    """
    # Process all PDFs and extract transactions
    all_transactions = process_all_pdfs(SOURCE_DIR)

    print(f"Total Transactions: {len(all_transactions)}")

    # Convert the list of transaction dictionaries into a DataFrame
    df = pd.DataFrame(all_transactions)

    # Standardize the Column Names
    df = standardize_column_names(df)

    # Add Amount column for post processing
    df = handle_credits_charges(df)

    # Robust file_path handling
    if "file_path" not in df.columns:
        df["file_path"] = ""
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
