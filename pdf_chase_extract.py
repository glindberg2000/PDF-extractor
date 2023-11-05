"""PDF Data Extractor for Chase VISA Statements.

This script serves as a starting point for handling Chase VISA statement format, 2023 version.
It reads transaction data from PDF statements and exports it to Excel and CSV files.

usage:
python pdf_chase_extract.py

"""

import os
import re
import pandas as pd
from PyPDF2 import PdfReader
from datetime import datetime

SOURCE_DIR = "SourceStatements/Chase"
OUTPUT_PATH_CSV = "ConsolidatedReports/Chase_visa.csv"
OUTPUT_PATH_XLSX = "ConsolidatedReports/Chase_visa.xlsx"

# Initialize an empty DataFrame to store all the extracted data
all_data = pd.DataFrame()


def add_file_path(df, file_path):
    df["File Path"] = file_path
    return df


def clean_dates_enhanced(df):
    """Clean and format the 'Date of Transaction' field.

    Parameters:
        df (DataFrame): The DataFrame containing the transaction data.

    Returns:
        DataFrame: The DataFrame with a new formatted 'Date' field.
    """
    dates = []
    skipped_rows = []

    for index, row in df.iterrows():
        try:
            month, day = row["Date of Transaction"].split("/")
            year = row["Statement Year"]
            statement_month = row.get("Statement Month", None)

            if int(month) == 12 and statement_month == 1:
                year = int(year) - 1

            date = datetime(int(year), int(month), int(day))
            date = date.strftime("%Y-%m-%d")
            dates.append(date)
        except Exception as e:
            print(f"Skipping row {index} due to an error: {e}")
            skipped_rows.append(index)

    df["Date"] = dates

    if skipped_rows:
        print(f"Skipped rows: {skipped_rows}")

    return df


def extract_chase_statements(pdf_path, statement_date):
    """Extract transaction data from Chase PDF statements.

    Parameters:
        pdf_path (str): The path to the PDF statement.
        statement_date (str): The statement date in YYYY-MM-DD format.

    Returns:
        DataFrame: The DataFrame containing the extracted transaction data.
    """
    # pdf_reader = PdfFileReader(open(pdf_path, "rb"))
    pdf_reader = PdfReader(pdf_path)
    transactions = []
    statement_year, statement_month, _ = map(int, statement_date.split("-"))

    # for page_num in range(1, pdf_reader.getNumPages()):
    for page_num in range(1, len(pdf_reader.pages)):
        try:
            # text = pdf_reader.getPage(page_num).extractText()
            text = pdf_reader.pages[page_num].extract_text()
            lines = text.split("\n")
            for line in lines:
                match = re.match(r"(\d{2}/\d{2})\s+(.+?)\s+([\d,]+\.\d{2})", line)
                if match:
                    date, description, amount = match.groups()
                    transactions.append([date, description, amount])
        except Exception as e:
            print(f"Skipping page {page_num + 1} due to read error {e}.")

    df = pd.DataFrame(
        transactions,
        columns=[
            "Date of Transaction",
            "Merchant Name or Transaction Description",
            "$ Amount",
        ],
    )
    # Rename '$ Amount' to 'Amount'

    df["Statement Date"] = statement_date
    df["Statement Year"] = statement_year
    df["Statement Month"] = statement_month

    # Standardize the amount by removing commas and converting to float
    df.rename(columns={"$ Amount": "Amount"}, inplace=True)
    df["Amount"] = df["Amount"].replace({",": ""}, regex=True).astype(float)

    # Add the file path to the DataFrame
    df = add_file_path(df, pdf_path)

    # Clean and format the dates
    df = clean_dates_enhanced(df)

    return df


# def main():
#     """Main function to loop through all PDF files in a directory and extract data."""
#     all_data = pd.DataFrame()
#     for filename in os.listdir(SOURCE_DIR):
#         if filename.endswith(".pdf") and "statements" in filename:
#             statement_date = filename.split("-")[0]
#             statement_date = (
#                 f"{statement_date[:4]}-{statement_date[4:6]}-{statement_date[6:8]}"
#             )
#             pdf_path = os.path.join(SOURCE_DIR, filename)
#             print(f"Processing {pdf_path}...")
#             df = extract_chase_statements(pdf_path, statement_date)
#             all_data = pd.concat([all_data, df])

#     # Remove extraneous columns and sort by the 'Date' field
#     all_data.drop(columns=["Statement Year", "Statement Month"], inplace=True)
#     all_data_sorted = all_data.sort_values(by="Date")

#     # Save to Excel and CSV files
#     all_data_sorted.to_excel(OUTPUT_PATH_XLSX, index=False)
#     all_data_sorted.to_csv(OUTPUT_PATH_CSV, index=False)


# if __name__ == "__main__":
#     main()


def main():
    all_data = pd.DataFrame()
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith(".pdf") and "statements" in filename:
            statement_date = filename.split("-")[0]
            statement_date = (
                f"{statement_date[:4]}-{statement_date[4:6]}-{statement_date[6:8]}"
            )
            pdf_path = os.path.join(SOURCE_DIR, filename)
            print(f"Processing {pdf_path}...")
            df = extract_chase_statements(pdf_path, statement_date)
            all_data = pd.concat([all_data, df], ignore_index=True)

    # Save to Excel and CSV files
    all_data.to_excel(OUTPUT_PATH_XLSX, index=False)
    all_data.to_csv(OUTPUT_PATH_CSV, index=False)


if __name__ == "__main__":
    main()
