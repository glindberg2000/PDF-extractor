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

SOURCE_DIR = PARSER_INPUT_DIRS["wellsfargo_mastercard"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["wellsfargo_mastercard"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["wellsfargo_mastercard"]["xlsx"]


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

    This function extracts the date from the filename of a PDF bank statement, formats it, and then updates
    the transaction dictionary with this statement date and the path of the PDF file. If the transaction dictionary
    has a 'date' field with a datetime object, it strips the time part, leaving only the date.

    Parameters
    ----------
    transaction : dict
        The transaction dictionary to be updated.
    pdf_path : str
        The file path of the PDF bank statement.

    Returns
    -------
    dict
        The updated transaction dictionary with the 'Statement Date' and 'File Path' included.

    Raises
    ------
    ValueError
        If the date in the filename does not match the expected format MMDDYY.

    Examples
    --------
    >>> transaction = {'date': datetime(2023, 1, 4), 'amount': 200.00}
    >>> pdf_path = '/path/to/statement010423.pdf'
    >>> add_statement_date_and_file_path(transaction, pdf_path)
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

    base_name = os.path.basename(pdf_path).split(".")[0]
    date_str = base_name[:6]
    try:
        statement_date = datetime.strptime(date_str, "%m%d%y").date()
    except ValueError:
        raise ValueError(
            f"Date in filename {base_name} does not match expected format MMDDYY."
        )

    # Add or update the statement date and file path in the transaction dictionary
    transaction["statement_date"] = statement_date.strftime("%Y-%m-%d")
    transaction["file_path"] = pdf_path
    # Remove the time part from the date if present
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


def export_transactions_to_files(transactions_list, csv_file_path, excel_file_path):
    """
    Export the list of transaction dictionaries to CSV and Excel files.

    This function converts a list of transaction dictionaries into a pandas DataFrame and then exports the data to
    the specified CSV and Excel file paths. It prints out the paths where the files are exported.

    Parameters
    ----------
    transactions_list : list of dict
        The list of transaction dictionaries to be exported.
    csv_file_path : str
        The file path where the CSV file will be saved.
    excel_file_path : str
        The file path where the Excel file will be saved.

    Returns
    -------
    None

    Examples
    --------
    >>> transactions_list = [{'transaction_date': '2023-01-04', 'post_date': '2023-01-04','reference':'REF123455','description': 'Grocery Store', 'amount': 50.00}]
    >>> csv_file_path = '/path/to/transactions.csv'
    >>> excel_file_path = '/path/to/transactions.xlsx'
    >>> export_transactions_to_files(transactions_list, csv_file_path, excel_file_path)
    Transactions exported to CSV at /path/to/transactions.csv
    Transactions exported to Excel at /path/to/transactions.xlsx
    """

    # Convert the list of transaction dictionaries into a DataFrame
    df_transactions = pd.DataFrame(transactions_list)

    # Export to CSV
    df_transactions.to_csv(csv_file_path, index=False)
    print(f"Transactions exported to CSV at {csv_file_path}")

    # Export to Excel
    df_transactions.to_excel(excel_file_path, index=False)
    print(f"Transactions exported to Excel at {excel_file_path}")


def main(source_dir, csv_output_path, xlsx_output_path):
    """Process all PDF bank statements and export transactions to CSV and Excel.

    Parameters:
    source_dir (str): The directory where PDF bank statements are located.
    csv_output_path (str): The file path for the output CSV file.
    xlsx_output_path (str): The file path for the output Excel file.
    """
    # Process all PDFs and extract transactions
    all_transactions = process_all_pdfs(source_dir)

    # Export the transactions to CSV and Excel
    export_transactions_to_files(all_transactions, csv_output_path, xlsx_output_path)

    print(f"Total Transactions {len(all_transactions)}")


def run():
    main(SOURCE_DIR, OUTPUT_PATH_CSV, OUTPUT_PATH_XLSX)


if __name__ == "__main__":
    run()
