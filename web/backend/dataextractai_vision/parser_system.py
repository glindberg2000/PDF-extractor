"""
PDF Statement Parser System
"""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Type
import pdfplumber
import fitz  # PyMuPDF
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Transaction:
    """Represents a financial transaction with source information."""

    date: str
    description: str
    amount: float
    category: str
    source_file: str
    page_number: int
    extracted_at: datetime


class BaseParser:
    """Base class for all statement parsers."""

    name: str = "base"
    description: str = "Base parser class"

    @classmethod
    def can_parse(cls, pdf_path: str, first_page_text: str) -> bool:
        """Check if this parser can handle the given PDF."""
        return False

    def extract_transactions(self, pdf_path: str) -> List[Transaction]:
        """Extract transactions from the PDF."""
        raise NotImplementedError


class WellsFargoBankParser(BaseParser):
    """Parser for Wells Fargo Bank statements."""

    name = "wellsfargo_bank"
    description = "Wells Fargo Bank Statement Parser"

    @classmethod
    def can_parse(cls, pdf_path: str, first_page_text: str) -> bool:
        """Check if this is a Wells Fargo bank statement."""
        logger.info("Checking if file is a Wells Fargo bank statement")
        logger.info(f"Looking for 'Wells Fargo' and 'Account Statement' in text")
        has_wells_fargo = "Wells Fargo" in first_page_text
        has_account_statement = "Account Statement" in first_page_text
        logger.info(f"Has 'Wells Fargo': {has_wells_fargo}")
        logger.info(f"Has 'Account Statement': {has_account_statement}")
        return has_wells_fargo and has_account_statement

    def extract_transactions(self, pdf_path: str) -> List[Transaction]:
        transactions = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    # Use pattern matching to find transactions
                    for line in text.split("\n"):
                        if re.match(r"^\d{1,2}/\d{1,2}", line):  # Date at start of line
                            try:
                                # Parse the line using Wells Fargo specific patterns
                                date_match = re.match(
                                    r"^(\d{1,2}/\d{1,2})\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.\d{2})",
                                    line,
                                )
                                if date_match:
                                    date_str, description, amount_str = (
                                        date_match.groups()
                                    )
                                    # Convert date to YYYY-MM-DD format
                                    date_obj = datetime.strptime(
                                        f"{datetime.now().year}/{date_str}", "%Y/%m/%d"
                                    )
                                    amount = float(amount_str.replace(",", ""))

                                    transaction = Transaction(
                                        date=date_obj.strftime("%Y-%m-%d"),
                                        description=description.strip(),
                                        amount=amount,
                                        category=self._guess_category(description),
                                        source_file=pdf_path,
                                        page_number=page_num,
                                        extracted_at=datetime.now(),
                                    )
                                    transactions.append(transaction)
                            except Exception as e:
                                logger.warning(f"Error parsing transaction line: {e}")
                                continue
        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            raise

        return transactions

    def _guess_category(self, description: str) -> str:
        """Make a best guess at the transaction category based on the description."""
        description = description.lower()

        categories = {
            "groceries": [
                "grocery",
                "food",
                "market",
                "safeway",
                "trader",
                "whole foods",
            ],
            "dining": ["restaurant", "cafe", "coffee", "starbucks"],
            "transport": ["uber", "lyft", "taxi", "transit", "parking"],
            "shopping": ["amazon", "target", "walmart", "costco"],
            "utilities": ["electric", "water", "gas", "internet", "phone"],
            "entertainment": ["netflix", "spotify", "hulu", "movie"],
            "transfer": ["transfer", "zelle", "venmo", "paypal"],
            "income": ["deposit", "salary", "direct dep"],
        }

        for category, keywords in categories.items():
            if any(keyword in description for keyword in keywords):
                return category

        return "other"


class WellsFargoVisaParser(BaseParser):
    """Parser for Wells Fargo Visa credit card statements."""

    name = "wellsfargo_visa"
    description = "Wells Fargo Visa Credit Card Statement Parser"

    @classmethod
    def can_parse(cls, pdf_path: str, first_page_text: str) -> bool:
        """Check if this is a Wells Fargo Visa statement."""
        logger.info("Checking if file is a Wells Fargo Visa statement")

        # Check for Wells Fargo branding and Visa indicators
        has_wells_fargo = "Wells Fargo" in first_page_text
        credit_card_indicators = [
            "Card Services",
            "Account ending in",
            "Cash Advance Limit",
            "Total Credit Limit",
            "Minimum Payment Warning",
        ]

        found_indicators = [
            indicator
            for indicator in credit_card_indicators
            if indicator in first_page_text
        ]
        logger.info(f"Found Visa card indicators: {found_indicators}")

        is_visa = has_wells_fargo and len(found_indicators) >= 2
        logger.info(f"Is Visa statement: {is_visa}")

        return is_visa

    def extract_transactions(self, pdf_path: str) -> List[Transaction]:
        transactions = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    text = page.extract_text()
                    logger.debug(f"Processing page {page_num}")
                    logger.debug("-" * 80)
                    logger.debug(text)
                    logger.debug("-" * 80)

                    # Split into lines and process each line
                    lines = text.split("\n")
                    for i, line in enumerate(lines):
                        try:
                            # Look for transaction patterns:
                            # 1. Regular purchase: MM/DD MM/DD Description Amount
                            # 2. Payment: MM/DD Description Amount
                            # 3. Interest/Fees: Description Amount (usually at end of statement)

                            # Try regular purchase pattern first
                            purchase_match = re.match(
                                r"^(\d{2}/\d{2})\s+\d{2}/\d{2}\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.\d{2})\s*$",
                                line.strip(),
                            )
                            if purchase_match:
                                date_str, description, amount_str = (
                                    purchase_match.groups()
                                )
                            else:
                                # Try payment pattern
                                payment_match = re.match(
                                    r"^(\d{2}/\d{2})\s+(.+?)\s+([-]?\d{1,3}(?:,\d{3})*\.\d{2})\s*$",
                                    line.strip(),
                                )
                                if payment_match:
                                    date_str, description, amount_str = (
                                        payment_match.groups()
                                    )
                                else:
                                    # Try interest/fees pattern
                                    interest_match = re.match(
                                        r"^(INTEREST CHARGE|LATE FEE|ANNUAL FEE).*?\s+([-]?\d{1,3}(?:,\d{3})*\.\d{2})\s*$",
                                        line.strip(),
                                    )
                                    if interest_match:
                                        description = interest_match.group(1)
                                        amount_str = interest_match.group(2)
                                        # Use statement end date for interest charges
                                        date_str = datetime.now().strftime("%m/%d")
                                    else:
                                        continue

                            # Clean up amount and convert to float
                            amount_str = amount_str.replace(",", "")
                            amount = float(amount_str)

                            # Convert date to YYYY-MM-DD format
                            date_obj = datetime.strptime(
                                f"{datetime.now().year}/{date_str}", "%Y/%m/%d"
                            )

                            # Create transaction
                            transaction = Transaction(
                                date=date_obj.strftime("%Y-%m-%d"),
                                description=description.strip(),
                                amount=amount,
                                category=self._guess_category(description),
                                source_file=pdf_path,
                                page_number=page_num,
                                extracted_at=datetime.now(),
                            )
                            transactions.append(transaction)
                            logger.debug(f"Found transaction: {transaction}")

                        except Exception as e:
                            logger.warning(
                                f"Error parsing line {i+1} on page {page_num}: {e}"
                            )
                            logger.warning(f"Line content: {line}")
                            continue

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}")
            raise

        return transactions

    def _guess_category(self, description: str) -> str:
        """Make a best guess at the transaction category based on the description."""
        description = description.lower()

        categories = {
            "groceries": [
                "grocery",
                "food",
                "market",
                "safeway",
                "trader",
                "whole foods",
                "costco",
                "target",
                "walmart",
                "amazon fresh",
            ],
            "dining": [
                "restaurant",
                "cafe",
                "coffee",
                "starbucks",
                "doordash",
                "uber eats",
                "grubhub",
                "mcdonalds",
                "burger",
                "pizza",
                "thai",
                "sushi",
            ],
            "transport": [
                "uber",
                "lyft",
                "taxi",
                "transit",
                "parking",
                "bart",
                "muni",
                "clipper",
                "gas",
                "shell",
                "chevron",
                "76",
                "arco",
            ],
            "shopping": [
                "amazon",
                "target",
                "walmart",
                "costco",
                "ebay",
                "etsy",
                "best buy",
                "apple",
                "nike",
                "adidas",
                "clothing",
            ],
            "utilities": [
                "electric",
                "water",
                "gas",
                "internet",
                "phone",
                "mobile",
                "verizon",
                "at&t",
                "comcast",
                "xfinity",
                "pg&e",
            ],
            "entertainment": [
                "netflix",
                "spotify",
                "hulu",
                "disney",
                "movie",
                "theatre",
                "amazon prime",
                "apple tv",
                "hbo",
                "showtime",
            ],
            "travel": [
                "airline",
                "flight",
                "hotel",
                "airbnb",
                "vrbo",
                "expedia",
                "delta",
                "united",
                "southwest",
                "marriott",
                "hilton",
            ],
            "health": [
                "pharmacy",
                "cvs",
                "walgreens",
                "medical",
                "doctor",
                "dental",
                "healthcare",
                "fitness",
                "gym",
            ],
            "payment": ["payment", "bill pay", "autopay"],
            "fees": ["fee", "interest charge", "late fee", "annual fee"],
        }

        for category, keywords in categories.items():
            if any(keyword in description.lower() for keyword in keywords):
                return category

        return "other"


class ParserRegistry:
    """Registry of available PDF parsers."""

    def __init__(self):
        self.parsers: List[Type[BaseParser]] = []

    def register(self, parser_class: Type[BaseParser]):
        """Register a new parser."""
        self.parsers.append(parser_class)

    def get_parser(self, pdf_path: str) -> Optional[BaseParser]:
        """Find the appropriate parser for a PDF."""
        try:
            # Extract first page text for parser detection
            doc = fitz.open(pdf_path)
            first_page = doc[0]
            first_page_text = first_page.get_text()
            doc.close()

            # Log the first page text for debugging
            logger.info(f"First page text from {pdf_path}:")
            logger.info("-" * 80)
            logger.info(first_page_text)
            logger.info("-" * 80)

            # Try each parser
            for parser_class in self.parsers:
                logger.info(f"Trying parser: {parser_class.name}")
                if parser_class.can_parse(pdf_path, first_page_text):
                    logger.info(f"Parser {parser_class.name} can handle this file")
                    return parser_class()
                else:
                    logger.info(f"Parser {parser_class.name} cannot handle this file")

            logger.warning(f"No suitable parser found for {pdf_path}")
            return None

        except Exception as e:
            logger.error(f"Error detecting parser for {pdf_path}: {e}")
            return None


# Initialize the parser registry
registry = ParserRegistry()

# Register available parsers
registry.register(WellsFargoBankParser)
registry.register(WellsFargoVisaParser)


def process_pdf(pdf_path: str) -> List[Transaction]:
    """Process a PDF file and extract transactions."""
    logger.info(f"Starting to process PDF: {pdf_path}")

    # First read the first page to help with parser detection
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page = pdf.pages[0]
            first_page_text = first_page.extract_text()
            logger.info("First page text extracted for parser detection:")
            logger.info("-" * 80)
            logger.info(first_page_text)
            logger.info("-" * 80)
    except Exception as e:
        logger.error(f"Error reading first page of PDF: {e}")
        raise

    parser = registry.get_parser(pdf_path)
    if not parser:
        logger.error(f"No suitable parser found for {pdf_path}")
        logger.error("Available parsers:")
        for p in registry.parsers:
            logger.error(f"- {p.name}: {p.description}")
        raise ValueError(f"No suitable parser found for {pdf_path}")

    logger.info(f"Selected parser: {parser.name} ({parser.description})")
    transactions = parser.extract_transactions(pdf_path)
    logger.info(f"Extracted {len(transactions)} transactions")
    return transactions
