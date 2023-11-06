"""
PDF Data Extractor for Bank of America Bank Statements

This script serves as a starting point for handling Bank of America's bank format.
It reads transaction data from PDF statements and exports it to Excel and CSV files.
The script scans through each page of each PDF file, extracts the relevant information,
and then sorts the transactions by date.

Usage:
    python bofa_bank_parser.py
"""
import pdfplumber
import pandas as pd
import re
import os
import glob

SOURCE_DIR = "data/input/bofa_bank"
OUTPUT_PATH_CSV = "data/output/bofa_bank_statements.csv"  # need to update the AI_category to applie different filter for BofA
OUTPUT_PATH_XLSX = "data/output/bofa_bank_statements.xlsx"


def add_statement_date_and_file_path(df, file_path):
    base_name = os.path.basename(file_path)
    # The filename is expected to have one underscore, separating "eStmt" from the date
    parts = base_name.split(".")[0].split("_")
    if len(parts) == 2:
        _, date_str = parts
        statement_date = pd.to_datetime(date_str).date()
    else:
        raise ValueError(
            f"Filename {base_name} does not match expected format 'eStmt_YYYY-MM-DD.pdf'."
        )

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
                    # amount = amount_match.group()
                    # For deposits and withdrawals sections:
                    amount = clean_amount(amount_match.group())
                    description = line[date_match.end() : amount_match.start()].strip()
                    if in_deposits_section:
                        deposits_additions.append((date, description, amount))
                    elif in_withdrawals_section:
                        withdrawals_subtractions.append((date, description, amount))
            elif in_checks_section:
                date_match = re.search(date_pattern, line)
                check_num_pattern = r"\d+"
                check_num_match = re.search(check_num_pattern, line)
                amount_match = re.search(amount_pattern, line)
                if date_match and check_num_match and amount_match:
                    date = date_match.group()
                    check_num = check_num_match.group().replace("Check #", "").strip()
                    amount = clean_amount(amount_match.group())
                    # amount = amount_match.group()
                    checks.append((date, check_num, amount))
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
    checks_df["Transaction Type"] = "Check"

    # Rename 'Check Number' column in checks_df to match the 'Description' column in the other DataFrames
    checks_df.rename(columns={"Check Number": "Description"}, inplace=True)

    # Concatenate the DataFrames into a single DataFrame
    combined_df = pd.concat([deposits_df, withdrawals_df, checks_df], ignore_index=True)

    return combined_df


def save_to_files(deposits_df, withdrawals_df, checks_df, base_filename):
    csv_deposit_path = f"{base_filename}_deposits.csv"
    csv_withdrawals_path = f"{base_filename}_withdrawals.csv"
    csv_checks_path = f"{base_filename}_checks.csv"
    excel_path = f"{base_filename}.xlsx"
    deposits_df.to_csv(csv_deposit_path, index=False)
    withdrawals_df.to_csv(csv_withdrawals_path, index=False)
    checks_df.to_csv(csv_checks_path, index=False)
    with pd.ExcelWriter(excel_path) as writer:
        deposits_df.to_excel(writer, sheet_name="Deposits and Additions", index=False)
        withdrawals_df.to_excel(
            writer, sheet_name="Withdrawals and Subtractions", index=False
        )
        checks_df.to_excel(writer, sheet_name="Checks", index=False)
    return csv_deposit_path, csv_withdrawals_path, csv_checks_path, excel_path


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


# Let's extract the text from the pages starting from the fourth page line by line to understand the layout.
def extract_checks_section(pdf_path):
    checks_section_lines = []  # To hold lines from the checks section
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # We'll start from the fourth page, where the checks section is expected
            for page in pdf.pages[3:]:
                text = page.extract_text()
                if (
                    text and "Checks" in text
                ):  # If 'Checks' is in the text, we process that page
                    for line in text.split("\n"):
                        checks_section_lines.append(line)
    except Exception as e:
        checks_section_lines.append(f"An exception occurred: {e}")

    return checks_section_lines


def main():
    all_transactions = []
    for file_path in glob.glob(os.path.join(SOURCE_DIR, "*.pdf")):
        text_list = extract_text_from_pdf(file_path)
        transactions_df = parse_transactions(text_list)
        transactions_df = add_statement_date_and_file_path(transactions_df, file_path)
        all_transactions.append(transactions_df)

    # Concatenate all transactions into a single DataFrame
    combined_transactions_df = pd.concat(all_transactions, ignore_index=True)

    # Save to CSV and Excel
    combined_transactions_df.to_csv(OUTPUT_PATH_CSV, index=False)
    combined_transactions_df.to_excel(OUTPUT_PATH_XLSX, index=False)


def run():
    main()


if __name__ == "__main__":
    run()
