"""
Chase Checking Parser (Modular)

This module provides a modular, class-based parser for Chase checking/debit PDF statements.
Implements the BaseParser interface and is registered with the ParserRegistry for dynamic use.

Usage:
    from dataextractai.parsers.chase_checking import ChaseCheckingParser
    parser = ChaseCheckingParser()
    raw = parser.parse_file('path/to/file.pdf')
    df = parser.normalize_data(raw)

This parser is importable for CLI, Django, or other Python integrations.
"""

import os
import re
import pandas as pd
from PyPDF2 import PdfReader
from datetime import datetime
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.utils.logger import get_logger
from dataextractai.utils.utils import standardize_column_names, get_parent_dir_and_file

logger = get_logger("chase_checking_parser_modular")


class ChaseCheckingParser(BaseParser):
    """
    Modular parser for Chase Checking/Debit PDF statements.

    Implements the BaseParser interface for use in CLI, Django, or other systems.
    Registered as 'chase_checking' in the ParserRegistry.

    Example:
        parser = ChaseCheckingParser()
        raw = parser.parse_file('path/to/file.pdf')
        df = parser.normalize_data(raw)
    """

    def parse_file(self, input_path: str, config=None):
        """
        Extract raw transaction data from a single PDF file.

        Args:
            input_path (str): Path to the PDF file.
            config (dict, optional): Config dict (may include statement_date, etc.)

        Returns:
            List[Dict]: List of raw transaction dicts, one per transaction.
        """
        if config is None:
            config = {}
        statement_date = config.get("statement_date")
        if not statement_date:
            # Try to infer from filename: YYYYMMDD-...
            basename = os.path.basename(input_path)
            try:
                date_str = basename.split("-")[0]
                statement_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            except Exception:
                logger.warning(
                    f"Could not infer statement_date from filename: {basename}"
                )
                statement_date = "1970-01-01"
        statement_year, statement_month, _ = map(int, statement_date.split("-"))
        pdf_reader = PdfReader(input_path)
        transactions = []
        account_number = None
        date_re = re.compile(r"(\d{2}/\d{2})")
        number_re = re.compile(r"^-?[\d,]+\.\d{2}$")
        section_marker_re = re.compile(
            r"\*start\*.*|\*end\*.*|CHECKING SUMMARY|TRANSACTION DETAIL|SUMMARY OF",
            re.IGNORECASE,
        )

        def is_number(s):
            return bool(number_re.match(s.replace(",", "")))

        # Extract account number from any page
        for page_num in range(len(pdf_reader.pages)):
            text = pdf_reader.pages[page_num].extract_text()
            if not account_number:
                match = re.search(r"\b\d{12,}\b", text)
                if match:
                    account_number = match.group(0)
        # Extract transactions from all pages
        for page_num in range(len(pdf_reader.pages)):
            try:
                text = pdf_reader.pages[page_num].extract_text()
                lines = text.split("\n")
                clean_lines = [
                    l
                    for l in lines
                    if l.strip() and not section_marker_re.match(l.strip())
                ]
                i = 0
                while i < len(clean_lines):
                    line = clean_lines[i].strip()
                    if date_re.search(line):
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
                            desc = re.sub(
                                r"\*start\*.*|\*end\*.*|CHECKING SUMMARY|TRANSACTION DETAIL|SUMMARY OF",
                                "",
                                desc,
                                flags=re.IGNORECASE,
                            ).strip()
                            transactions.append(
                                {
                                    "Date of Transaction": date,
                                    "Merchant Name or Transaction Description": desc,
                                    "Amount": amount,
                                    "Balance": balance,
                                    "Statement Date": statement_date,
                                    "Statement Year": statement_year,
                                    "Statement Month": statement_month,
                                    "Account Number": account_number,
                                    "File Path": input_path,
                                }
                            )
                        else:
                            logger.warning(
                                f"[ColumnSplit] Skipped line (not enough tokens or invalid numbers): {tx_line}"
                            )
                        i = j
                    else:
                        i += 1
            except Exception as e:
                logger.error(f"Exception on page {page_num+1} of {input_path}: {e}")
        return transactions

    def normalize_data(self, raw_data):
        """
        Normalize extracted data to a standard schema and return as DataFrame.

        Args:
            raw_data (List[Dict]): Raw transaction dicts.

        Returns:
            pd.DataFrame: Normalized DataFrame with standardized columns.
        """
        df = pd.DataFrame(raw_data)
        if not df.empty:
            df["Amount"] = df["Amount"].replace({",": ""}, regex=True).astype(float)
            df = standardize_column_names(df)
            if "file_path" in df.columns:
                df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)
        return df

    @classmethod
    def can_parse(cls, file_path: str, **kwargs) -> bool:
        required_phrases = [
            "Chase Total Checking",
            "JPMorgan Chase Bank, N.A.",
            "Chase.com",
            "1-800-935-9935",
            "checking",  # Must include 'checking' somewhere
        ]
        try:
            reader = PdfReader(file_path)
            text = reader.pages[0].extract_text() or ""
            text_lower = text.lower()
            return all(phrase.lower() in text_lower for phrase in required_phrases)
        except Exception:
            return False


# Register the parser for dynamic use
ParserRegistry.register_parser("chase_checking", ChaseCheckingParser)
