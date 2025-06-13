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
from dataextractai.utils.utils import (
    standardize_column_names,
    get_parent_dir_and_file,
)
import json
from dateutil import parser as dateutil_parser
from dataextractai.utils.utils import extract_date_from_filename
from dataextractai.parsers_core.models import (
    TransactionRecord,
    StatementMetadata,
    ParserOutput,
)

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
        Extract raw transaction data from a single PDF file and return a ParserOutput object.
        """
        if config is None:
            config = {}
        original_filename = config.get("original_filename")
        meta = self.extract_metadata(input_path, original_filename=original_filename)
        statement_date = meta.get("statement_date")
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

        for page_num in range(len(pdf_reader.pages)):
            text = pdf_reader.pages[page_num].extract_text()
            if not account_number:
                match = re.search(r"\b\d{12,}\b", text)
                if match:
                    account_number = match.group(0)
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
                                    "Statement Year": (
                                        int(statement_date[:4])
                                        if statement_date
                                        else None
                                    ),
                                    "Statement Month": (
                                        int(statement_date[5:7])
                                        if statement_date
                                        else None
                                    ),
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
        # --- Canonical Output Construction ---
        tx_records = []
        for row in transactions:
            # Normalize date to ISO
            try:
                year = row.get("Statement Year")
                month_day = row.get("Date of Transaction")
                if year and month_day:
                    m, d = [int(x) for x in month_day.split("/")]
                    transaction_date = datetime(year, m, d).strftime("%Y-%m-%d")
                else:
                    transaction_date = None
            except Exception:
                transaction_date = None
            # Amount as float
            try:
                amount = float(row.get("Amount", 0.0))
            except Exception:
                amount = 0.0
            tx_records.append(
                TransactionRecord(
                    transaction_date=transaction_date,
                    amount=amount,
                    description=row.get("Merchant Name or Transaction Description", ""),
                    posted_date=None,
                    transaction_type=None,
                    extra={
                        "balance": row.get("Balance"),
                        "account_number": row.get("Account Number"),
                        "file_path": row.get("File Path"),
                        "source": "ChaseCheckingParser",
                    },
                )
            )
        metadata = StatementMetadata(
            statement_date=statement_date,
            original_filename=original_filename,
            account_number=account_number,
            bank_name="Chase",
            account_type="Checking",
            parser_name="ChaseCheckingParser",
            parser_version="1.0",
            currency="USD",
            extra={},
        )
        return ParserOutput(
            transactions=tx_records,
            metadata=metadata,
            schema_version="1.0",
            errors=None,
            warnings=None,
        )

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

    def extract_metadata(self, input_path: str, original_filename: str = None) -> dict:
        """
        Extract robust metadata fields from a Chase Checking PDF statement.
        Parameters:
            input_path (str): Path to the PDF file.
            original_filename (str, optional): Original filename if available (for modular format compatibility).
        Returns:
            dict: Metadata fields including:
                - bank_name (str): Always 'Chase'
                - account_type (str): Always 'checking'
                - parser_name (str): Always 'chase_checking'
                - file_type (str): Always 'pdf'
                - account_number (str or None): 12+ digit account number if found
                - statement_date (str or None): Statement date (YYYY-MM-DD) from content or filename
                - account_holder_name (str or None): Extracted name(s) from first page
                - address (str or None): Extracted address from first page
                - statement_period_start (str or None): Start date of statement period if found
                - statement_period_end (str or None): End date of statement period if found
        """

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

        def extract_statement_date_from_filename(filename):
            base = os.path.basename(filename)
            date_str = base.split("-")[0]
            if len(date_str) == 8:
                try:
                    dt = dateutil_parser.parse(date_str, fuzzy=True)
                    return dt.strftime("%Y-%m-%d")
                except Exception:
                    return None
            return None

        reader = PdfReader(input_path)
        first_page = reader.pages[0].extract_text()
        all_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        print(
            "\n[DEBUG] First page text (first 40 lines):\n"
            + "\n".join(first_page.split("\n")[:40])
        )
        meta = {}
        meta["bank_name"] = "Chase"
        meta["account_type"] = "checking"
        meta["parser_name"] = "chase_checking"
        meta["file_type"] = "pdf"
        meta["account_number"] = extract_account_number(all_text)
        name, address = extract_name_and_address(first_page)
        meta["account_holder_name"] = name
        meta["address"] = address
        # --- Robust statement period extraction ---
        period_start, period_end = None, None
        try:
            # Use robust extraction from parser module
            statement_period_text = first_page
            # Try robust extraction for end date
            robust_end = extract_statement_date_from_content(input_path)
            if robust_end:
                period_end = robust_end
                print(
                    f"[DEBUG] Robust extraction succeeded for period_end: {period_end}"
                )
            else:
                print("[DEBUG] Robust extraction failed for period_end")
        except Exception as e:
            print(f"[DEBUG] Exception in robust extraction: {e}")

        # Fallback for statement_date
        statement_date = None
        # 1. Try period_end from content
        if period_end:
            statement_date = period_end
            print(f"[DEBUG] Using period_end as statement_date: {statement_date}")
        else:
            # 2. Try original_filename
            if original_filename:
                statement_date = extract_date_from_filename(original_filename)
                print(
                    f"[DEBUG] statement_date from original_filename: {statement_date}"
                )
            # 3. Try input_path filename
            if not statement_date:
                statement_date = extract_date_from_filename(input_path)
                print(f"[DEBUG] statement_date from input_path: {statement_date}")
            # 4. If still not found, set to None
            if not statement_date:
                print("[DEBUG] No valid statement_date found; setting to None")
                statement_date = None
        meta["statement_date"] = statement_date
        print("[DEBUG] Extracted metadata:\n", json.dumps(meta, indent=2))
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
