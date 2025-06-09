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

ChaseChecking Parser: Statement date extraction pattern
- Always extract the statement date from PDF content first (using parser-specific logic).
- Only fall back to extracting from the original_filename if provided and if content-based extraction fails.
- If both fail, log a warning and set statement_date to None (never raise).
- Do not assume the filename is always available or always in a specific format.
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
        # Require both 'Chase.com' (or 'chase.com') and 'Chase Sapphire Checking' on first or second page
        try:
            reader = PdfReader(file_path)
            max_pages = min(2, len(reader.pages))
            found_chase_com = False
            found_sapphire = False
            for i in range(max_pages):
                text = reader.pages[i].extract_text() or ""
                text_lower = text.lower()
                if "chase.com" in text_lower:
                    found_chase_com = True
                if "chase sapphire checking" in text_lower:
                    found_sapphire = True
            return found_chase_com and found_sapphire
        except Exception:
            return False

    def extract_metadata(self, input_path: str) -> dict:
        """
        Extract robust metadata fields from a Chase Checking PDF statement.

        Parameters:
            input_path (str): Path to the PDF file.

        Returns:
            dict: Metadata fields including:
                - bank_name (str): Always 'Chase'
                - account_type (str): Always 'checking'
                - parser_name (str): Always 'chase_checking'
                - file_type (str): Always 'pdf'
                - account_number (str or None): 12+ digit account number if found
                - statement_date (str or None): Statement date (YYYY-MM-DD) from filename
                - account_holder_name (str or None): Extracted name(s) from first page
                - address (str or None): Extracted address from first page
                - statement_period_start (str or None): Start date of statement period if found
                - statement_period_end (str or None): End date of statement period if found

        Example:
            >>> parser = ChaseCheckingParser()
            >>> meta = parser.extract_metadata('path/to/file.pdf')
            >>> print(meta['account_holder_name'])

        This method is robust to PDF quirks and works across all tested Chase Checking statements.
        """
        import re
        from PyPDF2 import PdfReader

        def extract_account_number(text):
            match = re.search(r"\b\d{12,}\b", text)
            if match:
                return match.group(0)
            return None

        def extract_name_and_address(first_page_text):
            skip_phrases = {
                "CUSTOMER SERVICE INFORMATION",
                "CHECKING SUMMARY",
                "TRANSACTION DETAIL",
            }
            customer_service_phrases = [
                "We accept operator relay calls",
                "International Calls",
                "Service Center:",
                "Para Espanol:",
                "1-713-262-1679",
                "1-888-262-4273",
            ]
            lines = [l.strip() for l in first_page_text.split("\n") if l.strip()]
            cleaned_lines = [
                re.sub(r"\s+", " ", l.replace("\xa0", " ")).strip() for l in lines
            ]

            def strip_customer_service(line):
                for phrase in customer_service_phrases:
                    line = line.replace(phrase, "")
                return line.strip()

            address = None
            address_idx = None
            for idx in range(len(cleaned_lines) - 1):
                street = cleaned_lines[idx]
                cityzip = cleaned_lines[idx + 1]
                if re.match(r"^\d+ .+", street) and re.search(
                    r"\d{5}(-\d{4})?", cityzip
                ):
                    address = street + " " + cityzip
                    address_idx = idx
                    break
            all_caps_names = []
            if address_idx is not None:
                for l in cleaned_lines[max(0, address_idx - 10) : address_idx]:
                    l_stripped = strip_customer_service(l)
                    matches = re.findall(r"[A-Z][A-Z .,'-]{2,}", l_stripped)
                    for m in matches:
                        if m not in skip_phrases and len(m.split()) >= 2:
                            all_caps_names.append(m)
            name = " ".join(all_caps_names) if all_caps_names else None
            return name, address

        def extract_statement_period(text):
            match = re.search(
                r"([A-Z][a-z]+ \d{1,2}, \d{4}) through ([A-Z][a-z]+ \d{1,2}, \d{4})",
                text,
            )
            if match:
                return match.group(1), match.group(2)
            return None, None

        def extract_statement_date_from_filename(filename):
            base = os.path.basename(filename)
            date_str = base.split("-")[0]
            if len(date_str) == 8:
                return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            return None

        reader = PdfReader(input_path)
        first_page = reader.pages[0].extract_text()
        all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        meta = {}
        meta["bank_name"] = "Chase"
        meta["account_type"] = "checking"
        meta["parser_name"] = "chase_checking"
        meta["file_type"] = "pdf"
        meta["account_number"] = extract_account_number(all_text)
        meta["statement_date"] = extract_statement_date_from_filename(input_path)
        name, address = extract_name_and_address(first_page)
        meta["account_holder_name"] = name
        meta["address"] = address
        period_start, period_end = extract_statement_period(first_page)
        meta["statement_period_start"] = period_start
        meta["statement_period_end"] = period_end
        return meta

    def extract_statement_date(self, pdf_text, original_filename=None):
        """
        Extract the statement date from PDF content. If not found, optionally try filename if original_filename is provided.
        Returns ISO date string (YYYY-MM-DD) or None.
        """
        import re
        from datetime import datetime

        # Try to extract date from PDF content (parser-specific logic)
        date_match = re.search(
            r"Statement Date:?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", pdf_text
        )
        if date_match:
            try:
                return (
                    datetime.strptime(date_match.group(1), "%m/%d/%Y")
                    .date()
                    .isoformat()
                )
            except Exception as e:
                print(f"[WARNING] Failed to parse statement date from PDF content: {e}")
        # Fallback: only use filename if explicitly provided
        if original_filename:
            fn_match = re.search(r"(20[0-9]{6})", original_filename)
            if fn_match:
                try:
                    return (
                        datetime.strptime(fn_match.group(1), "%Y%m%d")
                        .date()
                        .isoformat()
                    )
                except Exception as e:
                    print(
                        f"[WARNING] Failed to parse statement date from filename: {e}"
                    )
        print(
            "[WARNING] Could not extract statement date from PDF or filename. Setting to None."
        )
        return None


# Register the parser for dynamic use
ParserRegistry.register_parser("chase_checking", ChaseCheckingParser)
