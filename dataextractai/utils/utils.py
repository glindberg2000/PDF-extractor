# utils/utils.py

import re
import os
import pandas as pd
from dateutil import parser as dateutil_parser

from dataextractai.utils.config import (
    PARSER_OUTPUT_PATHS,
    COMMON_CONFIG,
    PERSONAL_EXPENSES,
    EXPENSE_THRESHOLD,
)

CONSOLIDATED_BATCH_PATH = PARSER_OUTPUT_PATHS["consolidated_batched"]["csv"]


def standardize_column_names(df):
    """
    Standardizes column names by:
    - Replacing spaces with underscores
    - Converting to lowercase
    - Removing special characters (except underscores)
    """
    df.columns = [re.sub(r"\W+", "_", col).strip("_").lower() for col in df.columns]
    return df


def get_parent_dir_and_file(path):
    # This function returns the file name and one directory up
    parent_directory, filename = os.path.split(path)  # Split the path and the file
    parent_directory_name = os.path.basename(
        parent_directory
    )  # Get the name of the parent directory
    return os.path.join(
        parent_directory_name, filename
    )  # Combine the parent directory name with the file name


def create_directory_if_not_exists(directory_path):
    """
    Create a directory if it does not exist.

    :param directory_path: Path of the directory to be created.
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        print(f"New batch file created at {directory_path}")
    except Exception as e:
        print(f"An error occurred while creating the directory: {e}")


def filter_by_keywords(df, keywords, exclude=True):
    """
    Filter transactions based on keywords.

    :param df: DataFrame containing transactions.
    :param keywords: List of keywords to include or exclude.
    :param exclude: Boolean, when True excludes transactions with given keywords,
                    when False includes them.
    :return: DataFrame after filtering.
    """

    def keyword_filter(description):
        return any(keyword.lower() in description.lower() for keyword in keywords)

    if exclude:
        return df[~df["description"].apply(keyword_filter)]
    else:
        return df[df["description"].apply(keyword_filter)]


def filter_by_amount(df, threshold):
    """
    Exclude transactions below a certain amount threshold.

    :param df: DataFrame containing transactions.
    :param threshold: Numeric threshold to filter transactions.
    :return: DataFrame after filtering.
    """
    return df[df["amount"] >= threshold]


# Example usage:
# df = pd.read_csv(CONSOLIDATED_BATCH_PATH)  # Load your DataFrame
# print(f"source df rows: {len(df)}")
# # excluded_keywords = [...]  # Your list of keywords to exclude
# # EXPENSE_THRESHOLD = 100  # Your expense threshold

# # Apply filters
# df_filtered = filter_by_keywords(df, PERSONAL_EXPENSES)
# df_filtered = filter_by_amount(df_filtered, EXPENSE_THRESHOLD)

# print(f"output df rows: {len(df_filtered)}")
# # Save the filtered DataFrame
# df_filtered.to_csv(CONSOLIDATED_BATCH_PATH, index=False)


def standardize_classifications(df, column_name="Amelia_AI_classification"):
    """
    Standardize the classification column based on certain keywords.

    :param df: DataFrame containing the data.
    :param column_name: The name of the classification column.
    :return: DataFrame with standardized classification values.
    """
    # Define the standardization rules
    rules = {
        "business": "Business Expense",
        "needs": "Needs Review",
        "personal": "Personal Expense",
    }

    # Apply the rules to the classification column
    for keyword, new_value in rules.items():
        df[column_name] = df[column_name].apply(
            lambda x: new_value if keyword in x.lower() else x
        )

    return df


# Example usage:
# df = pd.read_csv(CONSOLIDATED_BATCH_PATH)  # Load your DataFrame
# df_standardized = standardize_classifications(df)
# df_standardized.to_csv(CONSOLIDATED_BATCH_PATH, index=False)


def extract_date_from_filename(filename: str) -> str | None:
    """Extracts a YYYY-MM-DD date from an 8-digit sequence in the filename, if possible."""
    base = os.path.basename(filename)
    m = re.search(r"(\d{8})", base)
    if m:
        try:
            dt = dateutil_parser.parse(m.group(1), fuzzy=True)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


def extract_statement_date_from_content(pdf_path):
    """
    Extract statement end date from PDF content using robust fallback logic.
    Tries direct substring search, regexes, normalization, and pdfplumber fallback.
    Returns date as YYYY-MM-DD or None if not found.
    """
    from PyPDF2 import PdfReader
    import unicodedata
    from dateutil import parser as dateutil_parser

    try:
        reader = PdfReader(pdf_path)
    except Exception:
        return None
    # --- Direct substring search after 'through' in first page text ---
    try:
        first_page_text = reader.pages[0].extract_text() or ""
        idx = first_page_text.find("through")
        if idx != -1:
            after = first_page_text[idx + len("through") : idx + len("through") + 40]
            try:
                date = dateutil_parser.parse(after, fuzzy=True)
                return date.strftime("%Y-%m-%d")
            except Exception:
                pass
    except Exception:
        pass
    # --- Regex and normalization attempts on all pages ---
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        fixed_text = re.sub(r"(through)([A-Z])", r"\1 \2", text.replace("\n", ""))
        match = re.search(
            r"Statement Period\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text
        )
        if match:
            period_end = match.group(2)
            try:
                return pd.to_datetime(period_end, format="%m/%d/%Y").strftime(
                    "%Y-%m-%d"
                )
            except Exception:
                pass
        match = re.search(
            r"([A-Z][a-z]+ \d{1,2}, \d{4})\s*through\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
            fixed_text,
        )
        if match:
            period_end = match.group(2)
            try:
                return pd.to_datetime(period_end, format="%B %d, %Y").strftime(
                    "%Y-%m-%d"
                )
            except Exception:
                pass
        aggressive_text = re.sub(r"\s+", "", text)
        idx = aggressive_text.find("through")
        if idx != -1:
            after = aggressive_text[idx + len("through") : idx + len("through") + 40]
            try:
                date = dateutil_parser.parse(after, fuzzy=True)
                return date.strftime("%Y-%m-%d")
            except Exception:
                pass
        normalized_text = unicodedata.normalize("NFKD", aggressive_text)
        idx2 = normalized_text.find("through")
        if idx2 != -1:
            after = normalized_text[idx2 + len("through") : idx2 + len("through") + 40]
            try:
                date = dateutil_parser.parse(after, fuzzy=True)
                return date.strftime("%Y-%m-%d")
            except Exception:
                pass
    # --- Brute-force line search ---
    try:
        first_page_text = reader.pages[0].extract_text() or ""
        for line in first_page_text.splitlines():
            if "through" in line:
                after = line.split("through", 1)[1].strip()
                try:
                    date = dateutil_parser.parse(after, fuzzy=True)
                    return date.strftime("%Y-%m-%d")
                except Exception:
                    pass
    except Exception:
        pass
    # --- pdfplumber fallback ---
    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) > 0:
                plumber_text = pdf.pages[0].extract_text() or ""
                fixed_text = re.sub(
                    r"(through)([A-Z])", r"\1 \2", plumber_text.replace("\n", "")
                )
                match = re.search(
                    r"([A-Z][a-z]+ \d{1,2}, \d{4})\s*through\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
                    fixed_text,
                )
                if match:
                    period_end = match.group(2)
                    try:
                        return pd.to_datetime(period_end, format="%B %d, %Y").strftime(
                            "%Y-%m-%d"
                        )
                    except Exception:
                        pass
                aggressive_text = re.sub(r"\s+", "", plumber_text)
                idx = aggressive_text.find("through")
                if idx != -1:
                    after = aggressive_text[
                        idx + len("through") : idx + len("through") + 40
                    ]
                    try:
                        date = dateutil_parser.parse(after, fuzzy=True)
                        return date.strftime("%Y-%m-%d")
                    except Exception:
                        pass
    except Exception:
        pass
    return None
