"""PDF Data Extractor for Chase CHECKING/DEBIT Statements.

This script handles Chase checking/debit statement format (2023+).
It reads transaction data from PDF statements and exports it to Excel and CSV files.

usage:
python3 -m dataextractai.parsers.chase_checking_parser

"""

import os
import re
import pandas as pd
from PyPDF2 import PdfReader
from datetime import datetime
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from ..utils.utils import standardize_column_names, get_parent_dir_and_file
from ..utils.logger import get_logger
import argparse
import unicodedata
from dateutil import parser as dateutil_parser

SOURCE_DIR = PARSER_INPUT_DIRS["chase_visa"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["chase_visa"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["chase_visa"]["xlsx"]

# Initialize an empty DataFrame to store all the extracted data
all_data = pd.DataFrame()

# Robust logging setup: always use project-root 'logs' directory
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    log_dir = os.path.join(project_root, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.abspath(
        os.path.join(
            log_dir, f'chase_visa_parser-{datetime.now().strftime("%Y%m%d-%H%M%S")}.log'
        )
    )
    logging.basicConfig(
        filename=log_path,
        filemode="w",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    print(f"[LOGGING] Logging to: {log_path}")
    logging.info("--- Chase Visa Parser Run Started ---")
except Exception as e:
    print(f"[LOGGING ERROR] Could not set up logging: {e}")

logger = get_logger("chase_visa_parser")


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
            # print(f"Skipping row {index} due to an error: {e}")
            skipped_rows.append(index)

    df["Date"] = dates

    if skipped_rows:
        print(f"Skipped rows: {skipped_rows}")

    return df


def extract_account_number(text):
    # Look for a 12+ digit number (Chase account numbers are often 12-16 digits)
    match = re.search(r"\b\d{12,}\b", text)
    if match:
        return match.group(0)
    return None


def find_transaction_header(lines):
    # Look for a line with all keywords, case-insensitive
    keywords = ["DATE", "DESCRIPTION", "AMOUNT", "BALANCE"]
    for i, l in enumerate(lines):
        l_upper = l.upper()
        if all(k in l_upper for k in keywords):
            return i
    return None


def clean_description(desc):
    # Remove section markers and extra whitespace
    desc = re.sub(
        r"\*start\*.*|\*end\*.*|CHECKING SUMMARY|TRANSACTION DETAIL|SUMMARY OF",
        "",
        desc,
        flags=re.IGNORECASE,
    )
    return desc.strip()


def extract_statement_date_from_content(pdf_path):
    """
    Extract statement date from PDF content (statement period or explicit date fields). Only fall back to filename if content-based extraction fails. If both fail, return None.
    """
    print("[DEBUG] ENTERED extract_statement_date_from_content")
    reader = PdfReader(pdf_path)
    # --- NEW: Direct substring search after 'through' in full first page text (FIRST ATTEMPT) ---
    try:
        print("[DEBUG] ENTERED DIRECT SUBSTRING SEARCH block (FIRST)")
        first_page_text = reader.pages[0].extract_text() or ""
        idx = first_page_text.find("through")
        print(f"[DEBUG] Index of 'through': {idx}")
        if idx != -1:
            after = first_page_text[idx + len("through") : idx + len("through") + 40]
            print(
                f"[DEBUG] Direct substring after 'through' (repr): {repr(after)} (len={len(after)})"
            )
            try:
                date = dateutil_parser.parse(after, fuzzy=True)
                print(f"[DEBUG] Direct substring: parsed date: {date}")
                return date.strftime("%Y-%m-%d")
            except Exception as e:
                print(f"[DEBUG] Direct substring: failed to parse date: {e}")
        else:
            print("[DEBUG] 'through' not found in first_page_text")
    except Exception as e:
        print(f"[DEBUG] Direct substring fallback failed: {e}")
    # --- END NEW ---
    # Now proceed with all other extraction attempts as before
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if i == 0:
            print(
                "\n[DEBUG] First page text (first 40 lines):\n"
                + "\n".join(text.split("\n")[:40])
            )
        # Preprocess: insert a space after 'through' if immediately followed by a capital letter
        fixed_text = re.sub(r"(through)([A-Z])", r"\1 \2", text.replace("\n", ""))
        print("[DEBUG] fixed_text after preprocessing (repr):\n", repr(fixed_text))
        # Try to find statement period in MM/DD/YYYY format
        match = re.search(
            r"Statement Period\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})", text
        )
        if match:
            print(
                f"[DEBUG] Found Statement Period (MM/DD/YYYY): {match.group(1)} to {match.group(2)}"
            )
            period_end = match.group(2)
            try:
                return datetime.strptime(period_end, "%m/%d/%Y").strftime("%Y-%m-%d")
            except Exception as e:
                print(f"[DEBUG] Failed to parse period_end: {e}")
        # Try to find statement period in 'Month DD, YYYY through Month DD, YYYY' format, now robust to missing space
        match = re.search(
            r"([A-Z][a-z]+ \d{1,2}, \d{4})\s*through\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
            fixed_text,
        )
        if match:
            print(
                f"[DEBUG] Found Statement Period (long, robust): {match.group(1)} through {match.group(2)}"
            )
            period_end = match.group(2)
            try:
                return datetime.strptime(period_end, "%B %d, %Y").strftime("%Y-%m-%d")
            except Exception as e:
                print(f"[DEBUG] Failed to parse period_end (long, robust): {e}")
        # Aggressive normalization: remove all whitespace and newlines
        aggressive_text = re.sub(r"\s+", "", text)
        print(
            "[DEBUG] aggressive_text (all whitespace removed, repr):\n",
            repr(aggressive_text),
        )
        idx = aggressive_text.find("through")
        if idx != -1:
            print(
                "[DEBUG] Substring around 'through':",
                repr(aggressive_text[max(0, idx - 20) : idx + 40]),
            )
        match = re.search(
            r"([A-Z][a-z]+\d{1,2},\d{4})through([A-Z][a-z]+\d{1,2},\d{4})",
            aggressive_text,
        )
        if match:
            print(
                f"[DEBUG] Found Statement Period (aggressive): {match.group(1)} through {match.group(2)}"
            )
            period_end = match.group(2)
            try:
                period_end_spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", period_end)
                period_end_spaced = re.sub(
                    r"([a-zA-Z]+)(\d{1,2},)", r"\1 \2", period_end_spaced
                )
                print(f"[DEBUG] Aggressive period_end for parsing: {period_end_spaced}")
                return datetime.strptime(period_end_spaced, "%B %d, %Y").strftime(
                    "%Y-%m-%d"
                )
            except Exception as e:
                print(f"[DEBUG] Failed to parse period_end (aggressive): {e}")
        match = re.search(
            r"([A-Z][a-z]+\d{1,2},\d{4})through.*?([A-Z][a-z]+\d{1,2},\d{4})",
            aggressive_text,
        )
        if match:
            print(
                f"[DEBUG] Found Statement Period (non-greedy wildcard): {match.group(1)} through {match.group(2)}"
            )
            period_end = match.group(2)
            try:
                period_end_spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", period_end)
                period_end_spaced = re.sub(
                    r"([a-zA-Z]+)(\d{1,2},)", r"\1 \2", period_end_spaced
                )
                print(
                    f"[DEBUG] Non-greedy wildcard period_end for parsing: {period_end_spaced}"
                )
                return datetime.strptime(period_end_spaced, "%B %d, %Y").strftime(
                    "%Y-%m-%d"
                )
            except Exception as e:
                print(f"[DEBUG] Failed to parse period_end (non-greedy wildcard): {e}")
        normalized_text = unicodedata.normalize("NFKD", aggressive_text)
        print("[DEBUG] normalized_text (NFKD, repr):\n", repr(normalized_text))
        idx2 = normalized_text.find("through")
        if idx2 != -1:
            print(
                "[DEBUG] Substring around 'through' (normalized):",
                repr(normalized_text[max(0, idx2 - 20) : idx2 + 40]),
            )
        match = re.search(
            r"([A-Z][a-z]+\d{1,2},\d{4})through.*?([A-Z][a-z]+\d{1,2},\d{4})",
            normalized_text,
        )
        if match:
            print(
                f"[DEBUG] Found Statement Period (unicode normalized): {match.group(1)} through {match.group(2)}"
            )
            period_end = match.group(2)
            try:
                period_end_spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", period_end)
                period_end_spaced = re.sub(
                    r"([a-zA-Z]+)(\d{1,2},)", r"\1 \2", period_end_spaced
                )
                print(
                    f"[DEBUG] Unicode normalized period_end for parsing: {period_end_spaced}"
                )
                return datetime.strptime(period_end_spaced, "%B %d, %Y").strftime(
                    "%Y-%m-%d"
                )
            except Exception as e:
                print(f"[DEBUG] Failed to parse period_end (unicode normalized): {e}")
    # Fallback: brute-force search for 'through' and grab the rest of the line
    try:
        first_page_text = reader.pages[0].extract_text() or ""
        for line in first_page_text.splitlines():
            if "through" in line:
                after = line.split("through", 1)[1].strip()
                print(f"[DEBUG] Brute-force: text after 'through': {repr(after)}")
                try:
                    date = dateutil_parser.parse(after, fuzzy=True)
                    print(f"[DEBUG] Brute-force: parsed date: {date}")
                    return date.strftime("%Y-%m-%d")
                except Exception as e:
                    print(f"[DEBUG] Brute-force: failed to parse date: {e}")
    except Exception as e:
        print(f"[DEBUG] Brute-force fallback failed: {e}")
    # If all PyPDF2 attempts fail, try pdfplumber as a fallback for the first page only
    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) > 0:
                plumber_text = pdf.pages[0].extract_text() or ""
                print(
                    "[DEBUG] pdfplumber first page text (repr):\n", repr(plumber_text)
                )
                # Repeat the same regex attempts on plumber_text
                fixed_text = re.sub(
                    r"(through)([A-Z])", r"\1 \2", plumber_text.replace("\n", "")
                )
                aggressive_text = re.sub(r"\s+", "", plumber_text)
                normalized_text = unicodedata.normalize("NFKD", aggressive_text)
                # Try all regexes in order
                for candidate_text, label in [
                    (fixed_text, "fixed_text"),
                    (aggressive_text, "aggressive_text"),
                    (normalized_text, "normalized_text"),
                ]:
                    match = re.search(
                        r"([A-Z][a-z]+ \d{1,2}, \d{4})\s*through\s*([A-Z][a-z]+ \d{1,2}, \d{4})",
                        candidate_text,
                    )
                    if match:
                        print(
                            f"[DEBUG] pdfplumber {label} (long, robust): {match.group(1)} through {match.group(2)}"
                        )
                        period_end = match.group(2)
                        try:
                            return datetime.strptime(period_end, "%B %d, %Y").strftime(
                                "%Y-%m-%d"
                            )
                        except Exception as e:
                            print(
                                f"[DEBUG] pdfplumber {label} failed to parse period_end: {e}"
                            )
                    match = re.search(
                        r"([A-Z][a-z]+\d{1,2},\d{4})through([A-Z][a-z]+\d{1,2},\d{4})",
                        candidate_text,
                    )
                    if match:
                        print(
                            f"[DEBUG] pdfplumber {label} (aggressive): {match.group(1)} through {match.group(2)}"
                        )
                        period_end = match.group(2)
                        try:
                            period_end_spaced = re.sub(
                                r"([a-z])([A-Z])", r"\1 \2", period_end
                            )
                            period_end_spaced = re.sub(
                                r"([a-zA-Z]+)(\d{1,2},)", r"\1 \2", period_end_spaced
                            )
                            print(
                                f"[DEBUG] pdfplumber {label} aggressive period_end for parsing: {period_end_spaced}"
                            )
                            return datetime.strptime(
                                period_end_spaced, "%B %d, %Y"
                            ).strftime("%Y-%m-%d")
                        except Exception as e:
                            print(
                                f"[DEBUG] pdfplumber {label} failed to parse period_end (aggressive): {e}"
                            )
                    match = re.search(
                        r"([A-Z][a-z]+\d{1,2},\d{4})through.*?([A-Z][a-z]+\d{1,2},\d{4})",
                        candidate_text,
                    )
                    if match:
                        print(
                            f"[DEBUG] pdfplumber {label} (non-greedy wildcard): {match.group(1)} through {match.group(2)}"
                        )
                        period_end = match.group(2)
                        try:
                            period_end_spaced = re.sub(
                                r"([a-z])([A-Z])", r"\1 \2", period_end
                            )
                            period_end_spaced = re.sub(
                                r"([a-zA-Z]+)(\d{1,2},)", r"\1 \2", period_end_spaced
                            )
                            print(
                                f"[DEBUG] pdfplumber {label} non-greedy wildcard period_end for parsing: {period_end_spaced}"
                            )
                            return datetime.strptime(
                                period_end_spaced, "%B %d, %Y"
                            ).strftime("%Y-%m-%d")
                        except Exception as e:
                            print(
                                f"[DEBUG] pdfplumber {label} failed to parse period_end (non-greedy wildcard): {e}"
                            )
    except Exception as e:
        print(f"[DEBUG] pdfplumber fallback failed: {e}")
    print(
        "[DEBUG] No statement date found in content; will fall back to filename if possible."
    )
    return None


def extract_statement_date_from_filename(pdf_path):
    fname = os.path.basename(pdf_path)
    m = re.search(r"(\d{8})", fname)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


def extract_chase_statements(pdf_path, statement_date=None):
    """
    Extract Chase Checking statement transactions. Statement date extraction prioritizes PDF content, then filename, else None.
    """
    if not statement_date:
        statement_date = extract_statement_date_from_content(pdf_path)
        if not statement_date:
            statement_date = extract_statement_date_from_filename(pdf_path)
    skipped_pages = 0
    pdf_reader = PdfReader(pdf_path)
    transactions = []
    statement_year, statement_month, _ = (
        map(int, statement_date.split("-")) if statement_date else (None, None, None)
    )
    account_number = None
    pages_with_transactions = []
    tx_count_per_page = []
    date_re = re.compile(r"(\d{2}/\d{2})")
    number_re = re.compile(r"^-?[\d,]+\.\d{2}$")
    section_marker_re = re.compile(
        r"\*start\*.*|\*end\*.*|CHECKING SUMMARY|TRANSACTION DETAIL|SUMMARY OF",
        re.IGNORECASE,
    )

    def is_number(s):
        return bool(number_re.match(s.replace(",", "")))

    for page_num in range(len(pdf_reader.pages)):
        text = pdf_reader.pages[page_num].extract_text()
        if not account_number:
            account_number = extract_account_number(text)
    logger.info(f"Account number for {pdf_path}: {account_number}")
    for page_num in range(len(pdf_reader.pages)):
        try:
            text = pdf_reader.pages[page_num].extract_text()
            lines = text.split("\n")
            clean_lines = [
                l for l in lines if l.strip() and not section_marker_re.match(l.strip())
            ]
            buffer = []
            i = 0
            while i < len(clean_lines):
                line = clean_lines[i].strip()
                # Only process lines with a date
                if date_re.search(line):
                    # Join lines until we have at least 4 tokens (date, desc, amount, balance)
                    tx_line = line
                    j = i + 1
                    while len(tx_line.split()) < 4 and j < len(clean_lines):
                        tx_line += " " + clean_lines[j].strip()
                        j += 1
                    tokens = tx_line.split()
                    if (
                        len(tokens) >= 4
                        and is_number(tokens[-1])
                        and is_number(tokens[-2])
                    ):
                        date = tokens[0]
                        amount = tokens[-2].replace(",", "")
                        balance = tokens[-1].replace(",", "")
                        desc = " ".join(tokens[1:-2])
                        desc = clean_description(desc)
                        transactions.append([date, desc, amount, balance])
                    else:
                        logger.warning(
                            f"[ColumnSplit] Skipped line (not enough tokens or invalid numbers): {tx_line}"
                        )
                    i = j
                else:
                    i += 1
            if transactions:
                pages_with_transactions.append(page_num + 1)
                tx_count_per_page.append(len(transactions))
            else:
                dump_path = f"logs/chase_tx_block_dump-{os.path.basename(pdf_path)}-page{page_num+1}.txt"
                with open(dump_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(clean_lines[:41]))
                logger.warning(
                    f"No transactions found on page {page_num+1} of {pdf_path}. Dumped lines to {dump_path}"
                )
        except Exception as e:
            logger.error(f"Exception on page {page_num+1} of {pdf_path}: {e}")
            skipped_pages += 1
    logger.info(f"Pages with transactions for {pdf_path}: {pages_with_transactions}")
    logger.info(f"Transaction counts per page: {tx_count_per_page}")
    if not transactions:
        for page_num in range(len(pdf_reader.pages)):
            text = pdf_reader.pages[page_num].extract_text()
            lines = text.split("\n")[:20]
            logger.info(
                f"First 20 lines of page {page_num+1} for {pdf_path}:\n"
                + "\n".join(lines)
            )
    df = pd.DataFrame(
        transactions,
        columns=[
            "Date of Transaction",
            "Merchant Name or Transaction Description",
            "Amount",
            "Balance",
        ],
    )
    print("\n[DEBUG] Full DataFrame after parsing:\n", df)
    df["Statement Date"] = statement_date
    df["Statement Year"] = statement_year
    df["Statement Month"] = statement_month
    df["Amount"] = df["Amount"].replace({",": ""}, regex=True).astype(float)
    df = add_file_path(df, pdf_path)
    df = clean_dates_enhanced(df)
    df["Account Number"] = account_number
    return df


def main(write_to_file=True, source_dir=None, output_csv=None, output_xlsx=None):
    """
    Main function to process Chase VISA statements.

    Parameters:
    write_to_file (bool): Whether to write output to files
    source_dir (str): Directory containing PDF files
    output_csv (str): Path to output CSV file
    output_xlsx (str): Path to output XLSX file

    Returns:
    DataFrame: Processed transaction data
    """
    logger.info(
        f"Processing source_dir: {source_dir if source_dir is not None else SOURCE_DIR}"
    )
    print(f"[DEBUG] source_dir: {source_dir if source_dir is not None else SOURCE_DIR}")
    print(
        f"[DEBUG] output_csv: {output_csv if output_csv is not None else OUTPUT_PATH_CSV}"
    )
    print(
        f"[DEBUG] output_xlsx: {output_xlsx if output_xlsx is not None else OUTPUT_PATH_XLSX}"
    )
    all_data = pd.DataFrame()
    file_list = os.listdir(source_dir if source_dir is not None else SOURCE_DIR)
    logger.info(f"Files in source_dir: {file_list}")
    print(f"[DEBUG] Files in source_dir: {file_list}")
    for filename in file_list:
        if filename.endswith(".pdf") and "statements" in filename:
            statement_date = filename.split("-")[0]
            statement_date = (
                f"{statement_date[:4]}-{statement_date[4:6]}-{statement_date[6:8]}"
            )
            pdf_path = os.path.join(
                source_dir if source_dir is not None else SOURCE_DIR, filename
            )
            logger.info(f"Processing File: {pdf_path}")
            print(f"Processing File: {pdf_path}...")
            try:
                df = extract_chase_statements(pdf_path, statement_date)
                logger.info(f"Extracted {len(df)} transactions from {filename}")
                print(f"Extracted {len(df)} transactions from {filename}")
                all_data = pd.concat([all_data, df], ignore_index=True)
            except Exception as e:
                logger.error(f"Exception processing {filename}: {e}")
                print(f"Exception processing {filename}: {e}")
    logger.info(f"Total Transactions: {len(all_data)}")
    print(f"Total Transactions:{len(all_data)}")
    print(f"[DEBUG] all_data shape: {all_data.shape}")

    # Standardize the Column Names
    df = standardize_column_names(all_data)
    if not df.empty and "file_path" in df.columns:
        df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)
    # Save to CSV and Excel
    if write_to_file:
        output_csv_path = output_csv if output_csv is not None else OUTPUT_PATH_CSV
        output_xlsx_path = output_xlsx if output_xlsx is not None else OUTPUT_PATH_XLSX
        output_dir = os.path.dirname(output_csv_path)
        if not os.path.exists(output_dir):
            print(f"[DEBUG] Output directory does not exist, creating: {output_dir}")
            os.makedirs(output_dir, exist_ok=True)
        else:
            print(f"[DEBUG] Output directory exists: {output_dir}")
        print(f"[DEBUG] Writing to CSV: {output_csv_path}")
        print(f"[DEBUG] Writing to XLSX: {output_xlsx_path}")
        df.to_csv(output_csv_path, index=False)
        df.to_excel(output_xlsx_path, index=False)
        logger.info(f"Wrote CSV: {output_csv_path}")
        logger.info(f"Wrote XLSX: {output_xlsx_path}")

    logger.info("--- Chase Visa Parser Run Finished ---")
    return df


def run(write_to_file=True, input_dir=None, output_paths=None):
    """
    Executes the main function to process PDF files and extract data.

    Parameters:
    write_to_file (bool): A flag to determine whether the output DataFrame should be
    written to CSV and XLSX files. Defaults to True.
    input_dir (str, optional): Directory containing PDF files. If None, uses default.
    output_paths (dict, optional): Dictionary containing output paths. If None, uses default.

    Returns:
    DataFrame: A pandas DataFrame generated by the main function.
    """
    print(f"[DEBUG] run() called with input_dir: {input_dir}")
    print(f"[DEBUG] run() called with output_paths: {output_paths}")
    # Use provided paths or fall back to defaults
    source_dir = input_dir if input_dir is not None else SOURCE_DIR
    if output_paths is not None:
        output_csv = output_paths.get("csv", OUTPUT_PATH_CSV)
        output_xlsx = output_paths.get("xlsx", OUTPUT_PATH_XLSX)
    else:
        output_csv = OUTPUT_PATH_CSV
        output_xlsx = OUTPUT_PATH_XLSX
    print(
        f"[DEBUG] run() passing to main: source_dir={source_dir}, output_csv={output_csv}, output_xlsx={output_xlsx}"
    )
    return main(
        write_to_file=write_to_file,
        source_dir=source_dir,
        output_csv=output_csv,
        output_xlsx=output_xlsx,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Chase CHECKING/DEBIT PDF Statement Parser"
    )
    parser.add_argument(
        "--source_dir",
        type=str,
        default=None,
        help="Directory containing PDF files to process (Chase checking/debit statements)",
    )
    parser.add_argument(
        "--output_csv", type=str, default=None, help="Path to output CSV file"
    )
    parser.add_argument(
        "--output_xlsx", type=str, default=None, help="Path to output XLSX file"
    )
    parser.add_argument(
        "--no_write", action="store_true", help="If set, do not write output files"
    )
    args = parser.parse_args()

    output_paths = None
    if args.output_csv or args.output_xlsx:
        output_paths = {}
        if args.output_csv:
            output_paths["csv"] = args.output_csv
        if args.output_xlsx:
            output_paths["xlsx"] = args.output_xlsx

    run(
        write_to_file=not args.no_write,
        input_dir=args.source_dir,
        output_paths=output_paths,
    )
