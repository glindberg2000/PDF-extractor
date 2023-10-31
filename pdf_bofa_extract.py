
"""PDF Data Extractor for Bank of America VISA Statements.

This script reads transaction data from PDF statements and exports it to Excel and CSV files.
"""

import os
import re
import pandas as pd
from PyPDF2 import PdfFileReader
from datetime import datetime


def clean_dates(df):
    """Clean and format the 'Date of Transaction' field for Bank of America.

    Parameters:
        df (DataFrame): The DataFrame containing the transaction data.

    Returns:
        DataFrame: The DataFrame with a new formatted 'Date' field.
    """
    # Your logic for cleaning dates goes here
    return df


def extract_bofa_statements(pdf_path, statement_date):
    """Extract transaction data from Bank of America PDF statements.

    Parameters:
        pdf_path (str): The path to the PDF statement.
        statement_date (str): The statement date in YYYY-MM-DD format.

    Returns:
        DataFrame: The DataFrame containing the extracted transaction data.
    """
    # Your logic for extracting statements goes here
    return df


def main():
    """Main function to loop through all PDF files in a directory and extract data."""
    all_data = pd.DataFrame()
    directory_path = "EmilyCC/"
    for filename in os.listdir(directory_path):
        if filename.endswith(".pdf"):
            statement_date = filename.split("_")[1].split(".")[0]
            pdf_path = os.path.join(directory_path, filename)
            print(f"Processing {pdf_path}...")
            df = extract_bofa_statements(pdf_path, statement_date)
            all_data = pd.concat([all_data, df])

    # Remove extraneous columns and sort by the 'Date' field
    # all_data.drop(columns=['Your Columns Here'], inplace=True)
    all_data_sorted = all_data.sort_values(by="Date")

    # Save to Excel and CSV files
    all_data_sorted.to_excel("transactions_BOA_all.xlsx", index=False)
    all_data_sorted.to_csv("transactions_BOA_all.csv", index=False)


if __name__ == "__main__":
    main()
