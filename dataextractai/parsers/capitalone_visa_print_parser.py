"""
CapitalOne Visa Print Statement Parser (Modular)

This module provides a modular, class-based parser for CapitalOne Visa print-to-PDF statements.
Implements the BaseParser interface and is registered with the ParserRegistry for dynamic use.

Usage:
    from dataextractai.parsers.capitalone_visa_print_parser import CapitalOneVisaPrintParser
    parser = CapitalOneVisaPrintParser()
    raw = parser.parse_file('path/to/file.pdf')
    df = parser.normalize_data(raw)

This parser is importable for CLI, Django, or other Python integrations.
"""

import os
import re
import pandas as pd
import pdfplumber
from datetime import datetime
from dataextractai.parsers_core.base import BaseParser
from dataextractai.parsers_core.registry import ParserRegistry
from dataextractai.utils.logger import get_logger
from dataextractai.utils.utils import standardize_column_names, get_parent_dir_and_file

logger = get_logger("capitalone_visa_print_parser_modular")


class CapitalOneVisaPrintParser(BaseParser):
    """
    Modular parser for CapitalOne Visa print-to-PDF statements.

    Implements the BaseParser interface for use in CLI, Django, or other systems.
    Registered as 'capitalone_visa_print' in the ParserRegistry.

    Example:
        parser = CapitalOneVisaPrintParser()
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
        all_text = []
        # Try pdfplumber first for better text extraction
        try:
            with pdfplumber.open(input_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        all_text.append(text)
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}, falling back to PyPDF2.")
            from PyPDF2 import PdfReader

            pdf_reader = PdfReader(input_path)
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                    if text:
                        all_text.append(text)
                except Exception as e2:
                    logger.error(f"PyPDF2 error on page {page_num+1}: {e2}")
        full_text = "\n".join(all_text)
        logger.debug(f"Extracted text (first 500 chars): {full_text[:500]}")

        # Find the transaction table header
        header_pattern = re.compile(
            r"DATE\s+DESC\s*RIPTION\s+CATEGORY\s+CARD\s+AMOUN\s*T", re.IGNORECASE
        )
        header_match = header_pattern.search(full_text)
        if not header_match:
            logger.error("Could not find transaction table header in PDF text.")
            return []
        header_end = header_match.end()
        table_text = full_text[header_end:]

        # Split into lines, clean null bytes/non-printables, and parse transactions
        def clean_line(line):
            return (
                "".join(c for c in line if c.isprintable() and c != "\x00")
                .replace("\x00", "")
                .strip()
            )

        lines = [clean_line(l) for l in table_text.split("\n") if clean_line(l)]
        transactions = []
        buffer = []
        for line in lines:
            # New transaction starts with a month abbreviation
            if re.match(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", line):
                if buffer:
                    tx = self._parse_transaction_buffer(buffer, input_path)
                    if tx:
                        transactions.append(tx)
                    buffer = []
            buffer.append(line)
        # Parse the last transaction
        if buffer:
            tx = self._parse_transaction_buffer(buffer, input_path)
            if tx:
                transactions.append(tx)
        logger.info(f"Extracted {len(transactions)} transactions from {input_path}")
        return transactions

    def _parse_transaction_buffer(self, lines, input_path):
        """
        Parse a buffered list of lines into a transaction dict (robust for multi-line, minimal structure).
        Cleans null bytes and non-printable characters. Handles missing/invalid amounts.
        """
        joined = " ".join(lines)
        # Remove null bytes and non-printables
        joined = (
            "".join(c for c in joined if c.isprintable() and c != "\x00")
            .replace("\x00", "")
            .strip()
        )
        # Regex: date at start, amount at end, description in between
        pattern = re.compile(
            r"^(?P<date>[A-Za-z]{3,}(?: \d{1,2})?)\s+(?P<desc>.+?)\s+(-?\$?\d*[\d,]*\.\d{2}|-?\$)\.?$"
        )
        m = pattern.match(joined)
        if not m:
            # Try to find amount at end (even if just $ or -$)
            amount_match = re.search(r"(-?\$?\d*[\d,]*\.\d{2}|-?\$)\.?$", joined)
            date_match = re.match(
                r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b(?: \d{1,2})?",
                joined,
            )
            if amount_match and date_match:
                date = date_match.group(0).strip()
                amount = amount_match.group(1).replace("$", "").replace(",", "").strip()
                desc = joined[len(date) : amount_match.start()].strip()
            else:
                logger.warning(f"Could not parse transaction line: {joined}")
                return None
        else:
            date = m.group("date").strip()
            desc = m.group("desc").strip()
            amount = m.group(3).replace("$", "").replace(",", "").strip()
        # Normalize amount
        try:
            amount_val = float(amount) if amount and amount not in ["-", ""] else None
        except Exception:
            amount_val = None
        if not date:
            logger.warning(f"Missing date in transaction: {joined}")
            return None
        return {
            "transaction_date": date,
            "description": desc,
            "amount": amount_val,
            "file_path": input_path,
            "source": "capitalone_visa_print",
        }

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
            # TODO: Implement normalization logic for CapitalOne Visa print statements
            df = standardize_column_names(df)
            if "file_path" in df.columns:
                df["file_path"] = df["file_path"].apply(get_parent_dir_and_file)
        return df
