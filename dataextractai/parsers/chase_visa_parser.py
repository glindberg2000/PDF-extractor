"""
PDF Data Extractor for Chase VISA Statements.

This script serves as a starting point for handling Chase VISA statement format, 2023 version.
It reads transaction data from PDF statements and exports it to Excel and CSV files.

usage:
python3 -m dataextractai.parsers.chase_visa

"""

import os
import re
import pandas as pd
from PyPDF2 import PdfReader
from datetime import datetime
from typing import List, Dict, Any

from ..parsers_core.base import BaseParser
from ..parsers_core.registry import ParserRegistry
from ..parsers_core.models import ParserOutput, TransactionRecord, StatementMetadata
import argparse


class ChaseVisaParser(BaseParser):
    """
    Parses Chase VISA PDF statements.
    """

    def can_parse(self, file_path: str) -> bool:
        """
        Checks if the file is likely a Chase VISA PDF statement.
        A more robust implementation would check for specific keywords in the PDF.
        """
        return (
            "chase" in file_path.lower()
            and "visa" in file_path.lower()
            and file_path.endswith(".pdf")
        )

    def parse_file(self, input_path: str, config: Dict[str, Any] = None) -> List[Dict]:
        """
        Extracts transaction data from a Chase VISA PDF statement.
        """
        pdf_reader = PdfReader(input_path)
        transactions = []
        account_number = None
        statement_date = self._extract_statement_date(pdf_reader)

        date_re = re.compile(r"(\d{2}/\d{2})")
        number_re = re.compile(r"^-?[\d,]+\.\d{2}$")

        for page in pdf_reader.pages:
            text = page.extract_text() or ""
            if not account_number:
                account_number = self._extract_account_number(text)

            lines = text.split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if date_re.search(line):
                    tokens = line.split()
                    if len(tokens) >= 3 and self._is_number(tokens[-1]):
                        # Potential transaction line
                        date_str = tokens[0]
                        amount_str = tokens[-1]
                        description = " ".join(tokens[1:-1])

                        # Handle multi-line descriptions
                        j = i + 1
                        while (
                            j < len(lines)
                            and not date_re.search(lines[j])
                            and not self._is_number(
                                lines[j].split()[-1] if lines[j].split() else ""
                            )
                        ):
                            description += " " + lines[j].strip()
                            j += 1
                        i = j - 1

                        transactions.append(
                            {
                                "date_str": date_str,
                                "description": description.strip(),
                                "amount_str": amount_str.replace(",", ""),
                                "account_number": account_number,
                                "statement_date": statement_date,
                            }
                        )
                i += 1
        return transactions

    def normalize_data(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Normalizes the extracted data into the standard TransactionRecord format.
        """
        normalized_transactions = []
        for record in raw_data:
            statement_year = record["statement_date"].split("-")[0]
            month, day = record["date_str"].split("/")

            # Handle year change for transactions in December when statement is in January
            if int(month) == 12 and int(record["statement_date"].split("-")[1]) == 1:
                year = str(int(statement_year) - 1)
            else:
                year = statement_year

            full_date = f"{year}-{month}-{day}"

            normalized_transactions.append(
                {
                    "transaction_date": full_date,
                    "description": record["description"],
                    "amount": float(record["amount_str"]),
                    "extra": {"account_number": record["account_number"]},
                }
            )
        return normalized_transactions

    def _extract_statement_date(self, reader: PdfReader) -> str:
        # A simplified date extraction
        for page in reader.pages:
            text = page.extract_text() or ""
            match = re.search(r"Opening/Closing Date\s+[\d/]+\s+-\s+([\d/]+)", text)
            if match:
                return datetime.strptime(match.group(1), "%m/%d/%y").strftime(
                    "%Y-%m-%d"
                )
        return datetime.now().strftime("%Y-%m-%d")  # Fallback

    def _extract_account_number(self, text: str) -> str:
        match = re.search(r"Account Number:\s+([\d\s]+)", text)
        return match.group(1).replace(" ", "") if match else None

    def _is_number(self, s: str) -> bool:
        return bool(re.match(r"^-?[\d,]+\.\d{2}$", s))


def main(input_path: str) -> ParserOutput:
    """
    Main function for the parser, returns a ParserOutput object.
    """
    parser = ChaseVisaParser()
    errors = []

    try:
        raw_data = parser.parse_file(input_path)
        normalized_data = parser.normalize_data(raw_data)
        transactions = [TransactionRecord(**t) for t in normalized_data]

        # Extract metadata
        account_number = (
            normalized_data[0]["extra"]["account_number"] if normalized_data else None
        )
        statement_date = raw_data[0]["statement_date"] if raw_data else None

        metadata = StatementMetadata(
            parser_name="chase_visa_parser",
            bank_name="Chase",
            account_type="credit_card",
            account_number=account_number,
            statement_period_end=statement_date,
        )

        return ParserOutput(transactions=transactions, metadata=metadata)

    except Exception as e:
        errors.append(str(e))
        return ParserOutput(transactions=[], errors=errors)


# Register the parser class, not the main function
ParserRegistry.register_parser(name="chase_visa", parser_cls=ChaseVisaParser)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract Chase VISA statement transactions."
    )
    parser.add_argument("input_path", help="Path to a PDF file or a directory of PDFs.")
    args = parser.parse_args()
    main(input_path=args.input_path)
