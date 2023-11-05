import re
import pandas as pd
from datetime import datetime
import pdfplumber
import os
import pprint
import fitz  # PyMuPDF
import json
import csv

SOURCE_DIR = "SourceStatements/BOA_Bank"
OUTPUT_PATH_CSV = "ConsolidatedReports/BofA_bank.csv"
OUTPUT_PATH_XLSX = "ConsolidatedReports/Amazon_bank.xlsx"


def analyze_line_for_transaction_type(line):
    """
    Classify the transaction as deposit or withdrawal based on the spacing pattern.
    Assuming that a deposit will have 5 spaces until the EOL and withdrawals will have 3 spaces until EOL.

    :param analysis: List of tuples with the structure (type, length)
    :return: 'deposit' if it's likely a deposit, 'withdrawal' if it's likely a withdrawal
    """

    analysis = analyze_line_elements(line)

    # This will hold the classification and trailing value
    result = {"classification": "unknown"}

    last_spaces = next(
        (item for item in reversed(analysis) if item[0] == "spaces"), None
    )
    if last_spaces:
        # Determine the classification based on the number of spaces
        if last_spaces[1] == 5:
            result["classification"] = "deposit"
        elif last_spaces[1] == 3:
            result["classification"] = "withdrawal"

    return result


def analyze_line_for_transaction_type_all(line):
    """
    Classify the transaction as deposit or withdrawal based on the spacing pattern.
    For no balance rows:
    Deposit will have 5 spaces until the EOL and withdrawals will have 3 spaces until EOL:

    Deposit = #SSSSSE
    Withdrawal = #SSSE

    For single line rows with two monetary values:
    Deposit will have Number | 2 spaces | Number | EOL
    Withdrawal will have Number | 1 space | Number | EOL

    Deposit = #SS#SE
    Withdrawal = #S#SE

    :param line: The transaction line from the bank statement.
    :return: 'deposit' if it's likely a deposit, 'withdrawal' if it's likely a withdrawal
    """
    result = {}
    elements = analyze_line_elements(line)
    print(line, "\n")
    print(f"ELEMENTS: {elements}\n")
    result["elements"] = elements
    test_for_group = line
    # Check for number of monetary values
    monetary_values = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", test_for_group)

    # This will hold the classification and trailing value
    result["classification"] = "unknown"
    # Convert to a list comprehension of spaces
    spaces_elements = [item for item in elements if item[0] == "spaces"]
    last_spaces = spaces_elements[-1]
    second_last_spaces = spaces_elements[-2]
    # print(
    #     f"\nLast_spaces: {spaces_elements[-1]} 2nd last spaces: {spaces_elements[-2]}\n"
    # )

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
    print(
        f'Is MultiLine: {result["isMultiLine"]} \nClassification: {result["classification"]}\nDeposit = #SS#SE Withdrawal = #S#SE\n\n'
    )
    return result


def analyze_line_elements(line):
    # Example usage
    # lines = [
    #     "1/4 Forisus_Metrcobk Cardtobank 220103 From Card to Bank Account 200.00 4,712.05",
    #     "1/5 Transamerica Ins Inspayment 37L/A 6600026825 Gregory Lindberg 148.35 4,563.70",
    #     # Add more lines as needed
    # ]

    # for line in lines:
    #     result = analyze_line_elements(line)
    #     print(result)

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


def add_statement_date_and_file_path(df, pdf_path):
    # Extract the base name without extension
    base_name = os.path.basename(pdf_path).split(".")[0]

    # Assuming the date is at the beginning of the filename in MMDDYY format
    date_str = base_name[:6]
    try:
        # Parse the date. Adjust the format if the actual filename date format is different.
        statement_date = datetime.strptime(date_str, "%m%d%y").date()
    except ValueError:
        raise ValueError(
            f"Date in filename {base_name} does not match expected format MMDDYY."
        )

    # Add the statement date and file path columns
    df["Statement Date"] = statement_date
    df["File Path"] = pdf_path

    return df


def parse_transactions(text):
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
    # Join the lines and use regex to extract the data
    transaction_text = " ".join(lines)
    test_for_group = transaction_text
    # Check for number of monetary values
    monetary_values = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}", test_for_group)
    transaction_analysis = {}
    transaction_analysis = analyze_line_for_transaction_type_all(transaction_text)

    # Working version except for inline integers in the Description
    pattern = re.compile(
        r"(?P<date>\d{1,2}/\d{1,2})\s+"  # Date
        r"(?:Check\s+(?P<check_number>\d+)\s+)?"  # Optional Check number
        r"(?P<description>.+?)\s+"  # Description (non-greedy match)
        r"(?P<deposits>-?\d{1,3}(?:,\d{3})*\.\d{2})?\s+"  # Optional Deposits (allowing negative)
        r"(?P<withdrawals>-?\d{1,3}(?:,\d{3})*\.\d{2})?\s+"  # Optional Withdrawals (allowing negative)
        r"(?P<balance>-?\d{1,3}(?:,\d{3})*\.\d{2})",  # Balance (allowing negative)
        re.DOTALL,
    )
    # pattern = re.compile(
    #     r"(?P<date>\d{1,2}/\d{1,2})\s+"  # Date with one or more spaces after
    #     r"(?:Check\s+(?P<check_number>\d+)\s+)?"  # Optional Check number with spaces after
    #     r"(?P<description>.*?)"  # Description (non-greedy match)
    #     r"(?=\s+(?P<deposits>-?\d{1,3}(?:,\d{3})*\.\d{2})|\s+(?P<withdrawals>-?\d{1,3}(?:,\d{3})*\.\d{2})|\s+(?P<balance>-?\d{1,3}(?:,\d{3})*\.\d{2}))"  # Lookahead for deposits, withdrawals, or balance
    # )

    match = pattern.search(transaction_text)

    if match:
        # Extract data from the match object
        store_bal = match.group("balance")
        date_str = match.group("date")
        check_number = match.group("check_number") or ""
        description = match.group("description").strip()
        deposits = match.group("deposits") or "0.00"
        withdrawals = match.group("withdrawals") or "0.00"
        balance = match.group("balance") or "0.00"  # Set a default value if None

        if transaction_analysis["isMultiLine"]:
            if transaction_analysis["classification"] == "deposit":
                deposits = store_bal
            elif transaction_analysis["classification"] == "withdrawal":
                withdrawals = store_bal

        # Construct the transaction dictionary
        transaction_dict = {
            "date": datetime.strptime(date_str, "%m/%d").replace(
                year=2022
            ),  # Year is assumed
            "check_number": check_number,
            "description": description,
            "deposits": deposits,
            "withdrawals": withdrawals,
            "ending_daily_balance": balance,
        }
        return transaction_dict
    else:
        # If the pattern did not match, log the transaction block for review
        print(f"Could not parse transaction block: {' '.join(lines)}")
        print(transaction_text)
        print(f"ANALYSIS:{transaction_analysis}")
        # print(f"{analyze_line_elements(transaction_text)} \n")
        # Return an empty dictionary or a dictionary with specific keys and None values to avoid TypeError
        return {
            "date": None,
            "check_number": None,
            "description": None,
            "deposits": None,
            "withdrawals": None,
            "ending_daily_balance": None,
        }

        # print(f"Could not parse transaction block: {' '.join(lines)}")
        # return None


def find_balances_for_missing_transactions(transactions):
    last_transaction_balance_per_day = {}
    for transaction in transactions:
        # Skip transactions that are None or missing a 'date' key or have a None 'date'
        if (
            transaction is None
            or "date" not in transaction
            or transaction["date"] is None
        ):
            continue
        date = transaction["date"].date() if transaction["date"] else None
        balance = transaction.get("ending_daily_balance")
        if balance:  # If balance is not 0 or None
            last_transaction_balance_per_day[date] = balance
    return last_transaction_balance_per_day


def update_main_transaction_list(transactions, balances):
    """
    Update the main transaction list with the balances.
    """
    updated_transactions = []
    for transaction in transactions:
        # Skip transactions that are None or missing a 'date' key or have a None 'date'
        if (
            transaction is None
            or "date" not in transaction
            or transaction["date"] is None
        ):
            continue
        date = transaction["date"].date() if transaction["date"] else None
        if date in balances:
            transaction["ending_daily_balance"] = balances[date]
        updated_transactions.append(transaction)
    return updated_transactions


def extract_transactions_from_page(pdf_path):
    # Open the PDF file
    pdf_document = fitz.open(pdf_path)
    page = pdf_document[1]  # Assume transactions are on the second page
    page_text = page.get_text()
    pdf_document.close()  # Close the PDF after processing

    # Extract transactions from the page text
    parsed_transactions = parse_transactions(page_text)

    structured_transactions = []
    transactions_with_missing_balances = []

    # Process each transaction and collect those with missing balances
    for transaction_dict in parsed_transactions:
        if transaction_dict is None or len(transaction_dict) != 6:
            print(f"Unexpected transaction data: {transaction_dict}")
            continue  # Skip this transaction
        if len(transaction_dict) != 6:
            print(f"Unexpected transaction tuple length: {len(transaction_dict)}")
            print(transaction_dict)
            continue  # Skip this transaction
        # Check if the description is None before trying to strip it
        description = (
            transaction_dict["description"].strip()
            if transaction_dict["description"]
            else ""
        )

        # Use the processed values directly
        transaction_entry = {
            "date": transaction_dict["date"],  # Ensure this is a datetime object
            #    "description": transaction_dict["description"].strip(),
            "description": description,
            "deposits": transaction_dict["deposits"],
            "withdrawals": transaction_dict["withdrawals"],
            "ending_daily_balance": transaction_dict.get(
                "balance", 0
            ),  # Default to 0 if missing
        }

        # Collect transactions with missing balances for a second pass
        if transaction_entry["ending_daily_balance"] == 0:
            transactions_with_missing_balances.append(transaction_entry)

        structured_transactions.append(transaction_entry)

    # Perform a second pass to fill in missing balances
    updated_transactions_with_balances = find_balances_for_missing_transactions(
        structured_transactions
    )

    # Merge the updated transactions into the main list
    final_transaction_list = update_main_transaction_list(
        structured_transactions, updated_transactions_with_balances
    )

    # Convert to JSON
    json_data = json.dumps(final_transaction_list, default=str, indent=4)
    return json_data


# Call main function with your PDF path
# pdf_path = "SourceStatements/WF_Bank/013122 WellsFargo.pdf"
pdf_path = "SourceStatements/WF_Bank/022822 WellsFargo.pdf"
# pdf_path = "SourceStatements/WF_Bank/033122 WellsFargo.pdf"

extracted_page = extract_transactions_from_page(pdf_path)


print(
    f"extracted_transactions from fitz: {extracted_page}"
)  # This will display all transactions extracted

# extracted_transactions = extract_transactions_from_pdfminer(pdf_path)
# print(
#     f"extracted_transactions from pdfminer: {extracted_transactions}"
# )  # This will display all transactions extracted
