"""
PDF Data Extractor for Bank of America Statements

This script serves as a starting point for handling Bank of America's specific format.
It reads transaction data from PDF statements and exports it to Excel and CSV files.
The script scans through each page of each PDF file, extracts the relevant information,
and then sorts the transactions by date.

Usage:
    python bofa_visa_parser.py
"""

import os
import pandas as pd
import re
import PyPDF2
from PyPDF2 import PdfReader


SOURCE_DIR = "data/input/bofa_visa"
OUTPUT_PATH_CSV = "data/output/bofa_visa_statements.csv"
OUTPUT_PATH_XLSX = "data/output/bofa_visa_statements.xlsx"


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


def main():
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
            print(statement_date)
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
                    print(f"Skipping page {page_num + 1}")

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
    all_data["Transaction Date"] = pd.to_datetime(all_data["Transaction Date"])
    all_data["Posting Date"] = pd.to_datetime(all_data["Posting Date"])
    all_data["Statement Date"] = pd.to_datetime(all_data["Statement Date"])

    # Sort by "Transaction Date"
    all_data_sorted = all_data.sort_values(by="Transaction Date")

    # Save to Excel and CSV files
    all_data_sorted.to_excel(OUTPUT_PATH_XLSX, index=False)
    all_data_sorted.to_csv(OUTPUT_PATH_CSV, index=False)


def run():
    main()


if __name__ == "__main__":
    run()
