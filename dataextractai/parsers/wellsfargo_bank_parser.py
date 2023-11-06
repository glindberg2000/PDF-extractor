"""
This script processes PDF bank statements from Wells Fargo and extracts transactions into a structured data format. It scans the provided PDFs, identifies and parses transaction information, and then exports this data to both CSV and XLSX formats for further analysis.

The script is designed to handle multiple types of transaction entries, including those that span multiple lines, and to differentiate between deposits and withdrawals based on pattern recognition.

Author: Gregory Lindberg
Date: November 4, 2023

Usage:
   python3 -m dataextractai.parsers.wellsfargo_bank_parser
"""

__author__ = "Gregory Lindberg"
__version__ = "1.0"
__license__ = "MIT"
__description__ = (
    "Process Wells Fargo bank statement PDFs and extract transaction data."
)

import re
import pandas as pd
from datetime import datetime
import pdfplumber
import os
import pprint
import fitz  # PyMuPDF
import json
import csv
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from ..utils.utils import standardize_column_names

SOURCE_DIR = PARSER_INPUT_DIRS["wellsfargo_bank"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["wellsfargo_bank"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["wellsfargo_bank"]["xlsx"]


def analyze_line_for_transaction_type_all(line):
    """
    Analyze a line of text and determine the transaction type based on pattern recognition.

    Parameters:
    line : str, the line of text to analyze

    Returns:
    str, the determined transaction type ('deposit', 'withdrawal', or 'unknown')
    """
    result = {}
    elements = analyze_line_elements(line)
    test_for_group = line
    # Check for number of monetary values
    monetary_values = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", test_for_group)

    # This will hold the classification and trailing value
    result["classification"] = "unknown"
    # Convert to a list comprehension of spaces
    spaces_elements = [item for item in elements if item[0] == "spaces"]
    last_spaces = spaces_elements[-1]
    second_last_spaces = spaces_elements[-2]
    if len(monetary_values) == 1:
        result["isMultiLine"] = True
        if last_spaces:
            # Determine the classification based on the number of spaces
            if last_spaces[1] == 5:
                result["classification"] = "deposit"
            elif last_spaces[1] == 3:
                result["classification"] = "withdrawal"
    elif len(monetary_values) == 2:
        result["isMultiLine"] = False
        # Check the pattern for deposit and withdrawal based on space segments
        if second_last_spaces[1] == 2:
            result["classification"] = "deposit"
        elif second_last_spaces[1] == 1:
            result["classification"] = "withdrawal"
    return result


def analyze_line_elements(line):
    """
    Analyze the given line of text and categorize each segment as text, spaces, or numbers.

    This function uses a regular expression to identify different elements within a bank statement line.
    It categorizes each element as 'text' for strings, 'spaces' for whitespace, and 'number' for numerical values
    that represent transaction amounts. It adds an end-of-line character to the list of elements at the end.

    Parameters
    ----------
    line : str
        The line of text from a bank statement to be analyzed.

    Returns
    -------
    list of tuples
        A list of tuples where each tuple contains an element type ('text', 'spaces', 'number', or 'endoflinechar')
        and the length of that element in the line.

    Examples
    --------
    >>> line = "1/4 Forisus_Metrcobk Cardtobank 220103 From Card to Bank Account 200.00 4,712.05"
    >>> analyze_line_elements(line)
    [('text', 1), ('number', 1), ('text', 15), ('number', 6), ... , ('endoflinechar', 1)]
    """

    elements = []
    # Define a regex pattern to identify text, spaces, and numbers
    pattern = re.compile(r"([a-zA-Z]+)|(\s+)|(\d[\d,]*\.\d{2})")

    # Find all matches in the line
    matches = pattern.findall(line)

    for match in matches:
        text, spaces, number = match
        if text:
            elements.append(("text", len(text)))
        elif spaces:
            elements.append(("spaces", len(spaces)))
        elif number:
            elements.append(("number", len(number)))

    # Add an end of line character
    elements.append(("endoflinechar", len("\n")))

    return elements


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
        'date': '2023-01-04',
        'amount': 200.00,
        'Statement Date': '2023-01-04',
        'File Path': '/path/to/statement010423.pdf'
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
    transaction["Statement Date"] = statement_date.strftime("%Y-%m-%d")
    transaction["File Path"] = pdf_path
    # Remove the time part from the date if present
    if isinstance(transaction.get("date"), datetime):
        transaction["date"] = transaction["date"].date()

    return transaction


def parse_transactions(text):
    """
    Parse the provided text from a bank statement and extract transactions.

    This function splits the input text into lines and uses a regular expression to identify the start of a transaction by a date pattern. Each transaction is gathered into a block, which is then processed to extract detailed transaction data. Lines indicating 'Ending balance on' are ignored as they do not represent transaction entries.

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
    >>> text = "1/4 Grocery Store 50.00\n1/5 Online Payment Received 100.00\nEnding balance on 1/6"
    >>> parse_transactions(text)
    [{'Date': '1/4', 'Description': 'Grocery Store', 'Amount': 50.00},
     {'Date': '1/5', 'Description': 'Online Payment Received', 'Amount': 100.00}]
    """

    lines = text.split("\n")
    transactions = []
    current_transaction = []
    date_pattern = re.compile(
        r"^\d{1,2}/\d{1,2}"
    )  # Matches a date at the start of the line

    for line in lines:
        if date_pattern.match(line) or "Ending balance on" in line:
            if current_transaction:  # If we've gathered a transaction, process it
                transactions.append(process_transaction_block(current_transaction))
                current_transaction = []  # Reset for the next transaction
            if "Ending balance on" not in line:  # Ignore the "Ending balance on" line
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
        'date': datetime.date(2022, 1, 4),
        'description': 'Some Description',
        'deposits': '0.00',
        'withdrawals': '50.00',
        'ending_daily_balance': '1,500.00'
    }
    """

    transaction_text = " ".join(lines)
    transaction_analysis = analyze_line_for_transaction_type_all(transaction_text)

    monetary_values = re.findall(r"-?\d{1,3}(?:,\d{3})*\.\d{2}", transaction_text)
    if not monetary_values:
        # Handle error: no monetary values found
        return {}

    # Assume the last one or two monetary patterns are withdrawals/deposits and balance
    if transaction_analysis["isMultiLine"]:
        balance = None
        transaction_amount = monetary_values[-1]
        # Remove the last monetary value (the transaction amount) from the text
        transaction_text = transaction_text.rsplit(transaction_amount, 1)[0]
    else:
        balance = monetary_values[-1]
        transaction_amount = monetary_values[-2] if len(monetary_values) > 1 else "0.00"
        # Remove the last two monetary values (the transaction amount and the balance) from the text
        transaction_text = transaction_text.rsplit(transaction_amount, 1)[0].rsplit(
            balance, 1
        )[0]

    # Extract date
    date_match = re.search(r"\d{1,2}/\d{1,2}", transaction_text)
    if date_match:
        date_str = date_match.group()
        # Remove the date from the text to leave only the description
        description_text = transaction_text.split(date_str, 1)[1]
    else:
        # Handle error: no date found
        return {}

    # Clean up the description
    description = description_text.strip()

    # Classify the transaction as deposit or withdrawal
    if transaction_analysis["classification"] == "deposit":
        deposits = transaction_amount
        withdrawals = "0.00"
    elif transaction_analysis["classification"] == "withdrawal":
        withdrawals = transaction_amount
        deposits = "0.00"
    else:
        # Handle error: classification not found
        return {}

    # Construct the transaction dictionary
    transaction_dict = {
        "date": datetime.strptime(date_str, "%m/%d")
        .replace(year=2022)
        .date(),  # Convert to date to remove time part
        "description": description,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "ending_daily_balance": balance or "0.00",
    }

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
    >>> pdf_path = '/path/to/bank_statement.pdf'
    >>> json_data = extract_transactions_from_page(pdf_path)
    >>> print(json_data)
    "[{'date': '1/4', 'description': 'Grocery Store', 'amount': 50.00}, {'date': '1/5', 'description': 'Online Payment Received', 'amount': 100.00}]"
    """

    # Open the PDF file and extract the text from the second page
    with fitz.open(pdf_path) as pdf_document:
        page_text = pdf_document[1].get_text()

    # Extract transactions from the page text
    structured_transactions = parse_transactions(page_text)

    # Convert to JSON
    json_data = json.dumps(structured_transactions, default=str, indent=4)
    return json_data


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
        A list of transaction dictionaries, each containing transaction data and additional information like
        statement date and file path.

    Examples
    --------
    >>> source_dir = '/path/to/pdf/statements/'
    >>> all_transactions = process_all_pdfs(source_dir)
    >>> print(all_transactions[0])
    {
        'date': '2023-01-04',
        'description': 'Grocery Store',
        'amount': 50.00,
        'Statement Date': '2023-01-04',
        'File Path': '/path/to/pdf/statements/statement010423.pdf'
    }
    """
    all_transactions = []
    for filename in os.listdir(source_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(source_dir, filename)
            print(f"processing file: {filename}")
            transactions_json = extract_transactions_from_page(pdf_path)
            transactions_data = json.loads(transactions_json)
            # Add additional data like statement date
        for transaction in transactions_data:
            updated_transaction = add_statement_date_and_file_path(
                transaction, pdf_path
            )
            all_transactions.append(updated_transaction)

    return all_transactions


def convert_to_float(value):
    try:
        return float(value.replace(",", ""))
    except:
        return 0.0


def calculate_amount(row):
    deposit = convert_to_float(row["deposits"]) if not pd.isnull(row["deposits"]) else 0
    withdrawal = (
        convert_to_float(row["withdrawals"]) if not pd.isnull(row["withdrawals"]) else 0
    )
    return deposit - withdrawal  # Withdrawals are negative


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
    df["amount"] = df.apply(calculate_amount, axis=1)

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
