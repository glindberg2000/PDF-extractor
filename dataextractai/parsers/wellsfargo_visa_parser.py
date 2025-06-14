"""
This script processes PDF Visa statements from Wells Fargo and extracts transactions into a structured data format. It scans the provided PDFs, identifies and parses transaction information, and then exports this data to both CSV and XLSX formats for further analysis.

The script is designed to handle transaction entries across multiple pages and to differentiate between payments, purchases, and other charges based on statement structure.

Author: Gregory Lindberg
Date: March 16, 2025
"""

__author__ = "Gregory Lindberg"
__version__ = "1.0"
__license__ = "MIT"
__description__ = (
    "Process Wells Fargo Visa statement PDFs and extract transaction data."
)

import re
import pandas as pd
from datetime import datetime
import pdfplumber
import os
import logging
import json
from ..utils.config import PARSER_INPUT_DIRS, PARSER_OUTPUT_PATHS
from dataextractai.utils.utils import (
    extract_date_from_filename,
    standardize_column_names,
    get_parent_dir_and_file,
)
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
from dateutil import parser as dateutil_parser
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

SOURCE_DIR = PARSER_INPUT_DIRS["wellsfargo_visa"]
OUTPUT_PATH_CSV = PARSER_OUTPUT_PATHS["wellsfargo_visa"]["csv"]
OUTPUT_PATH_XLSX = PARSER_OUTPUT_PATHS["wellsfargo_visa"]["xlsx"]


def extract_statement_date(text):
    """Extract the statement period from the statement text."""
    match = re.search(
        r"Statement Period (\d{2}/\d{2}/\d{4}) to (\d{2}/\d{2}/\d{4})", text
    )
    if match:
        # Return the end date of the statement period
        date_str = match.group(2)
        # Convert from MM/DD/YYYY to YYYY-MM-DD
        date_obj = datetime.strptime(date_str, "%m/%d/%Y")
        return date_obj.strftime("%Y-%m-%d")
    return None


def extract_transactions(pdf_path):
    """Extract transactions from a Wells Fargo Visa PDF statement."""
    transactions = []
    statement_date = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Processing PDF: {pdf_path}")

            # Extract text from the first page to get statement date
            first_page_text = pdf.pages[0].extract_text()
            statement_date = extract_statement_date(first_page_text)
            logger.info(f"Statement date: {statement_date}")

            # Get all text from the document at once
            full_text = ""
            for page_num in range(len(pdf.pages)):
                full_text += pdf.pages[page_num].extract_text() + "\n"

            logger.debug("Full text extracted from PDF")

            # Extract payment transactions
            payment_transactions = extract_payment_transactions(
                full_text, statement_date
            )
            for transaction in payment_transactions:
                transaction["transaction_type"] = "payment"
                transaction["statement_date"] = statement_date
                transaction["file_path"] = pdf_path
                transactions.append(transaction)

            # Extract purchase transactions
            purchase_transactions = extract_purchase_transactions(
                full_text, statement_date
            )
            for transaction in purchase_transactions:
                transaction["transaction_type"] = "purchase"
                transaction["statement_date"] = statement_date
                transaction["file_path"] = pdf_path
                transactions.append(transaction)

    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {e}")

    logger.info(f"Found {len(transactions)} transactions")
    return transactions


def extract_payment_transactions(text, statement_date):
    """Extract payment transactions from the statement text."""
    transactions = []

    # Find the Payments section - look for the payment section header and gather until TOTAL PAYMENTS
    start_idx = text.find("Payments")
    end_idx = text.find("TOTAL PAYMENTS FOR THIS PERIOD")

    if start_idx == -1 or end_idx == -1:
        logger.debug("No payments section found")
        return transactions

    payments_section = text[start_idx:end_idx]
    logger.debug(f"Found payments section:\n{payments_section}")

    # Regular expression to match payment transactions
    pattern = r"(\d{2}/\d{2})\s+(\d{2}/\d{2})\s+([A-Z0-9]+)\s+(.*?)\s+(\d{1,3}(?:,\d{3})*\.\d{2})"

    matches = re.finditer(pattern, payments_section)
    for match in matches:
        trans_date, post_date, reference_number, description, amount = match.groups()

        # Convert dates to full dates using statement period year
        statement_year = datetime.strptime(statement_date, "%Y-%m-%d").year
        trans_date_full = f"{trans_date}/{statement_year}"
        post_date_full = f"{post_date}/{statement_year}"

        # Clean amount (remove commas)
        amount = float(amount.replace(",", ""))

        transaction = {
            "transaction_date": trans_date_full,
            "post_date": post_date_full,
            "reference_number": reference_number,
            "description": description.strip(),
            "amount": amount,
            "credits": amount,
            "charges": 0.0,
        }

        logger.debug(f"Found payment transaction: {transaction}")
        transactions.append(transaction)

    return transactions


def extract_purchase_transactions(text, statement_date):
    """Extract purchase transactions from the statement text."""
    transactions = []

    # Regular expression to match purchase transactions
    pattern = r"(\d{4})\s+(\d{2}/\d{2})\s+(\d{2}/\d{2})\s+([A-Z0-9]+)\s+(.*?)\s+(\d{1,3}(?:,\d{3})*\.\d{2})$"

    matches = re.finditer(pattern, text, re.MULTILINE)
    for match in matches:
        card_ending, trans_date, post_date, reference_number, description, amount = (
            match.groups()
        )

        # Convert dates to full dates using statement period year
        statement_year = datetime.strptime(statement_date, "%Y-%m-%d").year
        trans_date_full = f"{trans_date}/{statement_year}"
        post_date_full = f"{post_date}/{statement_year}"

        # Clean amount (remove commas)
        amount = float(amount.replace(",", ""))

        transaction = {
            "card_ending": card_ending,
            "transaction_date": trans_date_full,
            "post_date": post_date_full,
            "reference_number": reference_number,
            "description": description.strip(),
            "amount": -amount,  # negative since it's a charge
            "credits": 0.0,
            "charges": amount,
        }

        logger.debug(f"Found purchase transaction: {transaction}")
        transactions.append(transaction)

    return transactions


def update_transaction_years(transactions):
    """Update transaction years based on statement date to handle December-January transitions."""
    for transaction in transactions:
        # Skip if missing dates or statement date
        if not all(
            k in transaction
            for k in ["transaction_date", "post_date", "statement_date"]
        ):
            continue

        statement_date = datetime.strptime(transaction["statement_date"], "%Y-%m-%d")

        # Process transaction date
        try:
            trans_date = datetime.strptime(transaction["transaction_date"], "%m/%d/%Y")
            # If statement is in January and transaction is in December, use previous year
            if statement_date.month == 1 and trans_date.month == 12:
                trans_date = trans_date.replace(year=statement_date.year - 1)
            else:
                trans_date = trans_date.replace(year=statement_date.year)
            transaction["transaction_date"] = trans_date.strftime("%Y-%m-%d")
        except ValueError:
            logger.warning(
                f"Could not process transaction date: {transaction['transaction_date']}"
            )

        # Process post date
        try:
            post_date = datetime.strptime(transaction["post_date"], "%m/%d/%Y")
            # If statement is in January and post date is in December, use previous year
            if statement_date.month == 1 and post_date.month == 12:
                post_date = post_date.replace(year=statement_date.year - 1)
            else:
                post_date = post_date.replace(year=statement_date.year)
            transaction["post_date"] = post_date.strftime("%Y-%m-%d")
        except ValueError:
            logger.warning(f"Could not process post date: {transaction['post_date']}")

    return transactions


def process_all_pdfs(source_dir):
    """Process all PDFs in the source directory."""
    all_transactions = []

    for filename in os.listdir(source_dir):
        if filename.endswith(".pdf"):
            pdf_path = os.path.join(source_dir, filename)
            logger.info(f"Processing file: {filename}")

            transactions = extract_transactions(pdf_path)
            all_transactions.extend(transactions)

    # Update years based on statement dates
    all_transactions = update_transaction_years(all_transactions)

    return all_transactions


# CONTRACT-COMPLIANT ENTRYPOINT: main(input_path: str) -> ParserOutput
# This is the ONLY supported entrypoint. Do not add CLI/batch logic here.
def main(input_path: str) -> ParserOutput:
    """
    Canonical entrypoint for contract-based integration. Parses a single Wells Fargo Visa PDF and returns a ParserOutput.
    Accepts a single file path and returns a ParserOutput object. No directory or batch logic.
    All transaction_date and post_date fields are normalized to YYYY-MM-DD format.
    """
    parser = WellsFargoVisaParser()
    errors = []
    warnings = []
    try:
        raw_data = parser.parse_file(
            input_path, config={"original_filename": os.path.basename(input_path)}
        )
        df = parser.normalize_data(raw_data)
        transactions = []
        for idx, row in df.iterrows():
            # Enforce normalization at the point of record creation
            norm_transaction_date = _normalize_date_to_yyyy_mm_dd(
                row.get("transaction_date")
            )
            norm_post_date = _normalize_date_to_yyyy_mm_dd(row.get("post_date"))
            if row.get("transaction_date") and norm_transaction_date is None:
                warnings.append(
                    f"[WARN] Could not normalize transaction_date '{row.get('transaction_date')}' at row {idx} in {input_path}"
                )
            if row.get("post_date") and norm_post_date is None:
                warnings.append(
                    f"[WARN] Could not normalize post_date '{row.get('post_date')}' at row {idx} in {input_path}"
                )
            try:
                tr = TransactionRecord(
                    transaction_date=norm_transaction_date,
                    amount=row.get("amount"),
                    description=row.get("description"),
                    posted_date=norm_post_date,
                    transaction_type=row.get("transaction_type"),
                    extra={
                        k: v
                        for k, v in row.items()
                        if k
                        not in [
                            "transaction_date",
                            "amount",
                            "description",
                            "transaction_type",
                            "post_date",
                        ]
                    },
                )
                if not tr.transaction_date:
                    msg = f"[SKIP] File: {input_path}, Index: {idx}, Reason: missing or invalid transaction_date, Data: {row}"
                    warnings.append(msg)
                    continue
                transactions.append(tr)
            except Exception as e:
                import traceback

                tb = traceback.format_exc()
                msg = f"TransactionRecord validation error at row {idx} in {input_path}: {e}\n{tb}"
                errors.append(msg)
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        msg = f"Exception in file {input_path}: {e}\n{tb}"
        errors.append(msg)
        transactions = []
        df = None
    # Build metadata
    meta = parser.extract_metadata(
        input_path, original_filename=os.path.basename(input_path)
    )
    metadata = StatementMetadata(
        statement_date=meta.get("statement_date"),
        statement_period_start=meta.get("statement_period_start"),
        statement_period_end=meta.get("statement_period_end"),
        statement_date_source=meta.get("date_source", "content"),
        original_filename=os.path.basename(input_path),
        account_number=meta.get("account_number"),
        bank_name=meta.get("bank_name", "Wells Fargo"),
        account_type=meta.get("account_type", "credit_card"),
        parser_name=meta.get("parser_name", parser.name),
        parser_version=None,
        currency="USD",
        extra=None,
    )
    output = ParserOutput(
        transactions=transactions,
        metadata=metadata,
        schema_version="1.0",
        errors=errors if errors else None,
        warnings=warnings if warnings else None,
    )
    # Final Pydantic validation
    try:
        ParserOutput.model_validate(output.model_dump())
    except Exception as e:
        import traceback

        tb = traceback.format_exc()
        msg = f"Final ParserOutput validation error: {e}\n{tb}"
        errors.append(msg)
        output.errors = errors
        raise
    import logging

    logger = logging.getLogger("wellsfargo_visa_parser")
    logger.info(
        f"SUMMARY for {input_path}: created={len(transactions)}, errors={len(errors)}, warnings={len(warnings)}"
    )
    return output


def _normalize_date_to_yyyy_mm_dd(val):
    """Convert MM/DD/YYYY or other date strings to YYYY-MM-DD. Return None if invalid."""
    from datetime import datetime

    if not val or not isinstance(val, str):
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def run(write_to_file=True):
    """Run the parser."""
    return main(write_to_file=write_to_file)


class WellsFargoVisaParser(BaseParser):
    """
    Modular parser for Wells Fargo Visa PDF statements.
    Implements BaseParser for use in modular/AI pipeline.
    """

    name = "wellsfargo_visa"
    description = "Parser for Wells Fargo Visa PDF statements. Extracts and normalizes transactions."

    @staticmethod
    def extract_account_number_from_first_page(pdf_path):
        import re

        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = pdf.pages[0].extract_text() or ""
                match = re.search(r"Account ending in (\d{4})", text)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    def parse_file(self, input_path, config=None):
        if config is None:
            config = {}
        original_filename = config.get("original_filename")
        # Use robust extract_metadata to get statement_date and other metadata
        meta = self.extract_metadata(input_path, original_filename=original_filename)
        statement_date = meta.get("statement_date")
        print(f"[DEBUG] Using statement_date for all rows: {statement_date}")
        transactions = extract_transactions(input_path)
        transactions = update_transaction_years(transactions)
        # Extract account number from first page
        account_number = self.extract_account_number_from_first_page(input_path)
        for tx in transactions:
            tx["account_number"] = account_number
            tx["statement_date"] = statement_date
        return transactions

    def normalize_data(self, raw_data):
        # Use the existing DataFrame normalization logic
        df = pd.DataFrame(raw_data)
        if df.empty:
            return df
        df = standardize_column_names(df)
        if "file_path" in df.columns:
            df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)
        return df

    @classmethod
    def can_parse(cls, input_path):
        required_phrases = ["wellsfargo.com", "Account ending in", "Statement Period"]
        credit_card_markers = ["Minimum Payment", "Late Payment Warning", "SIGNATURE"]
        try:
            with pdfplumber.open(input_path) as pdf:
                first_page_text = pdf.pages[0].extract_text() or ""
                text_lower = first_page_text.lower()
                # All required phrases must be present
                if not all(phrase.lower() in text_lower for phrase in required_phrases):
                    return False
                # At least one credit card marker must be present
                if not any(
                    marker.lower() in text_lower for marker in credit_card_markers
                ):
                    return False
                return True
        except Exception:
            return False

    def extract_metadata(self, input_path: str, original_filename: str = None) -> dict:
        """
        Extract robust metadata fields from a Wells Fargo Visa PDF statement.
        Statement date extraction prioritizes PDF content (statement period or explicit date fields). Only falls back to original_filename, then input_path filename, if content-based extraction fails. If all fail, logs a warning and sets statement_date to None.
        """
        import re
        from PyPDF2 import PdfReader
        import os
        import logging

        logger = logging.getLogger("wellsfargo_visa_parser")

        def extract_statement_period(first_page_text):
            match = re.search(
                r"Statement Period\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})",
                first_page_text,
            )
            if match:
                return match.group(1), match.group(2)
            return None, None

        def extract_coupon_block(first_page_text):
            lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
            coupon_lines = lines[-40:]
            addr_idx = None
            for i, l in enumerate(coupon_lines):
                if re.match(r"\d+ [A-Z0-9 ]+", l):
                    addr_idx = i
                    break
            name = None
            address = None
            if (
                addr_idx is not None
                and addr_idx > 0
                and addr_idx + 1 < len(coupon_lines)
            ):
                name = coupon_lines[addr_idx - 1]
                address = coupon_lines[addr_idx] + ", " + coupon_lines[addr_idx + 1]
            acct_num = None
            for l in coupon_lines:
                m = re.search(r"Account Number\s*([\d ]{8,})", l)
                if m:
                    acct_num = m.group(1).replace(" ", "")
                    break
            return name, address, acct_num

        reader = PdfReader(input_path)
        first_page_text = reader.pages[0].extract_text() if reader.pages else ""
        period_start, period_end = extract_statement_period(first_page_text)
        # Robust statement date extraction
        statement_date = None
        date_source = "content"
        if period_end:
            try:
                statement_date = datetime.strptime(period_end, "%m/%d/%Y").strftime(
                    "%Y-%m-%d"
                )
            except Exception:
                statement_date = None
        if not statement_date:
            if original_filename:
                fname = original_filename
                date_source = "original_filename"
            else:
                fname = os.path.basename(input_path)
                date_source = "input_path"
            m = re.search(r"(\d{8})", fname)
            if m:
                try:
                    statement_date = datetime.strptime(m.group(1), "%Y%m%d").strftime(
                        "%Y-%m-%d"
                    )
                except Exception:
                    statement_date = None
            if not statement_date:
                logger.warning(
                    f"Could not extract statement date from content or {date_source} filename. Setting to None."
                )
        # Validate date
        try:
            if statement_date:
                _ = dateutil_parser.parse(statement_date)
            else:
                statement_date = None
        except Exception:
            logger.warning(
                f"Extracted statement_date is not a valid date: {statement_date}. Setting to None."
            )
            statement_date = None
        name, address, acct_num = extract_coupon_block(first_page_text)
        logger.info(f"Statement date source: {date_source}, value: {statement_date}")
        return {
            "bank_name": "Wells Fargo",
            "account_type": "credit_card",
            "parser_name": "wellsfargo_visa",
            "file_type": "pdf",
            "account_number": acct_num,
            "statement_date": statement_date,
            "account_holder_name": name,
            "address": address,
            "statement_period_start": period_start,
            "statement_period_end": period_end,
        }


# Register the parser
ParserRegistry.register_parser(WellsFargoVisaParser.name, WellsFargoVisaParser)

if __name__ == "__main__":
    run()
