"""
Vision-based PDF transaction extractor using GPT-4 Vision API.
"""

import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import hashlib
import sqlite3
from dataclasses import dataclass
from typing import NamedTuple

from openai import OpenAI
from pdf2image import convert_from_path
from PIL import Image
import base64
from io import BytesIO
import io
import httpx
import fitz
import pandas as pd

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler("extraction.log"), logging.StreamHandler()],
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


class ProcessingResult(NamedTuple):
    """Represents the result of processing a single page."""

    success: bool
    extracted_transactions: List[Transaction]
    error: Optional[str] = None


class ProcessingHistory:
    """Manages processing history and state."""

    def __init__(self, db_path: str = "processing_history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_history (
                    file_hash TEXT PRIMARY KEY,
                    file_path TEXT,
                    last_modified TIMESTAMP,
                    last_processed TIMESTAMP,
                    pages_processed INTEGER,
                    total_transactions INTEGER,
                    status TEXT
                )
            """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS page_results (
                    file_hash TEXT,
                    page_number INTEGER,
                    processed_at TIMESTAMP,
                    success BOOLEAN,
                    transactions_count INTEGER,
                    error_message TEXT,
                    FOREIGN KEY (file_hash) REFERENCES processing_history(file_hash),
                    PRIMARY KEY (file_hash, page_number)
                )
            """
            )

    def get_file_hash(self, file_path: str) -> str:
        """Generate a unique hash for a file based on path and modification time."""
        mtime = os.path.getmtime(file_path)
        return hashlib.md5(f"{file_path}:{mtime}".encode()).hexdigest()

    def needs_processing(self, file_path: str) -> bool:
        """Check if a file needs processing based on modification time."""
        file_hash = self.get_file_hash(file_path)
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "SELECT last_processed FROM processing_history WHERE file_hash = ?",
                (file_hash,),
            ).fetchone()
            return result is None

    def record_processing(
        self, file_path: str, pages_processed: int, total_transactions: int, status: str
    ):
        """Record the processing of a file."""
        file_hash = self.get_file_hash(file_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processing_history 
                (file_hash, file_path, last_modified, last_processed, pages_processed, total_transactions, status)
                VALUES (?, ?, ?, datetime('now'), ?, ?, ?)
            """,
                (
                    file_hash,
                    file_path,
                    os.path.getmtime(file_path),
                    pages_processed,
                    total_transactions,
                    status,
                ),
            )

    def record_page_result(
        self, file_path: str, page_number: int, result: ProcessingResult
    ):
        """Record the processing result of a single page."""
        file_hash = self.get_file_hash(file_path)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO page_results 
                (file_hash, page_number, processed_at, success, transactions_count, error_message)
                VALUES (?, ?, datetime('now'), ?, ?, ?)
            """,
                (
                    file_hash,
                    page_number,
                    result.success,
                    result.transactions_count,
                    result.error_message,
                ),
            )


class VisionExtractor:
    """Extracts transaction data from PDFs using GPT-4 Vision."""

    # Model configuration
    MODEL_NAME = "gpt-4.5-preview"  # The latest version that works with vision
    MAX_TOKENS = 1500
    TEMPERATURE = 0

    def __init__(self, api_key: str = None, force_reprocess: bool = False):
        """Initialize the extractor with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided or set in OPENAI_API_KEY environment variable"
            )

        # Initialize OpenAI client with a custom HTTP client
        http_client = httpx.Client()
        self.client = OpenAI(http_client=http_client)

        # Initialize processing history
        self.history = ProcessingHistory()
        self.force_reprocess = force_reprocess

        # Define the system prompt for transaction extraction
        self.EXTRACTION_PROMPT = """
        You are a financial document analysis expert. Your task is to extract transaction data from financial statements.
        
        Rules:
        1. Extract ONLY transaction entries (ignore headers, subtotals, totals, etc.)
        2. For each transaction, provide:
           - date: in YYYY-MM-DD format
           - description: full transaction description
           - amount: positive for credits, negative for debits
           - category: best-guess transaction category
        3. Ensure amounts are properly signed (negative for expenses/debits)
        4. Skip non-transaction entries (balances, fees, interest charges)
        5. Return a JSON array of transaction objects
        
        Example output format:
        [
            {
                "date": "2024-03-14",
                "description": "AMAZON.COM PURCHASE",
                "amount": -29.99,
                "category": "Shopping"
            }
        ]
        """

    def _resize_image_if_needed(self, image, max_size_mb=19):
        """Resize image if it exceeds the maximum size limit."""
        # Convert image to bytes to check size
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format="JPEG")
        img_byte_arr = img_byte_arr.getvalue()

        # Check if size exceeds limit
        size_mb = len(img_byte_arr) / (1024 * 1024)
        if size_mb > max_size_mb:
            # Calculate new dimensions to reduce size while maintaining aspect ratio
            ratio = (max_size_mb / size_mb) ** 0.5
            new_width = int(image.width * ratio)
            new_height = int(image.height * ratio)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        return image

    def extract_from_image(
        self, image_path: str, source_file: str, page_number: int
    ) -> ProcessingResult:
        """Extract transactions from a single image using GPT-4 Vision.

        Args:
            image_path: Path to the image file to process
            source_file: Original PDF file path
            page_number: Page number in the original PDF

        Returns:
            ProcessingResult containing success status and extracted transactions
        """
        try:
            # Open and process image
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # Resize if needed
                img = self._resize_image_if_needed(img)

                # Convert to base64
                buffered = io.BytesIO()
                img.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode()

                # Format the base64 string according to API requirements
                base64_image = f"data:image/jpeg;base64,{img_str}"

                logger.info(f"Processing page {page_number} of {source_file}")

                # Call the API
                response = self.client.chat.completions.create(
                    model=self.MODEL_NAME,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": self.EXTRACTION_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {"url": base64_image},
                                },
                            ],
                        }
                    ],
                    max_tokens=self.MAX_TOKENS,
                    temperature=self.TEMPERATURE,
                )

                raw_response = response.choices[0].message.content

                # Parse the response
                try:
                    transactions_data = json.loads(raw_response)

                    # Convert to Transaction objects with source information
                    transactions = []
                    for t in transactions_data:
                        transaction = Transaction(
                            date=t["date"],
                            description=t["description"],
                            amount=float(t["amount"]),
                            category=t["category"],
                            source_file=source_file,
                            page_number=page_number,
                            extracted_at=datetime.now(),
                        )
                        transactions.append(transaction)

                    logger.info(
                        f"Successfully extracted {len(transactions)} transactions from page {page_number}"
                    )
                    return ProcessingResult(
                        success=True, extracted_transactions=transactions, error=None
                    )

                except json.JSONDecodeError as e:
                    error_msg = (
                        f"Failed to parse JSON response on page {page_number}: {e}"
                    )
                    logger.error(error_msg)
                    logger.debug(f"Raw response: {raw_response}")
                    return ProcessingResult(
                        success=False, extracted_transactions=[], error=error_msg
                    )

        except Exception as e:
            error_msg = (
                f"Error processing page {page_number} of {source_file}: {str(e)}"
            )
            logger.error(error_msg)
            return ProcessingResult(
                success=False, extracted_transactions=[], error=error_msg
            )

    def process_pdf(self, pdf_path: str, output_dir: str) -> Optional[str]:
        """Process a single PDF file and extract transactions.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory to save the output CSV

        Returns:
            Path to the generated CSV file if successful, None otherwise
        """
        try:
            logging.info(f"Starting processing of PDF: {pdf_path}")

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Initialize variables for collecting results
            all_transactions = []

            # Get PDF document
            doc = fitz.open(pdf_path)

            # Process each page
            for page_num in range(doc.page_count):
                result = self._process_page(doc[page_num], pdf_path, page_num + 1)
                if result and result.extracted_transactions:
                    all_transactions.extend(result.extracted_transactions)

            # Close the document
            doc.close()

            # If we found transactions, save them to CSV
            if all_transactions:
                # Generate output filename
                pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
                csv_path = os.path.join(output_dir, f"{pdf_name}_transactions.csv")

                # Convert to DataFrame and save
                df = pd.DataFrame(all_transactions)
                df.to_csv(csv_path, index=False)
                return csv_path

        except Exception as e:
            logging.error(f"Error processing PDF {pdf_path}: {e}")

        return None

    def process_directory(self, input_dir: str, output_dir: str) -> List[str]:
        """Process all PDF files in a directory.

        Args:
            input_dir: Directory containing PDF files
            output_dir: Directory to save output CSV files

        Returns:
            List of paths to generated CSV files
        """
        # Get list of PDF files
        pdf_files = []
        for root, _, files in os.walk(input_dir):
            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, file))

        logging.info(f"Found {len(pdf_files)} PDF files to process in {input_dir}")

        # Process each PDF file
        csv_files = []
        for i, pdf_path in enumerate(pdf_files, 1):
            logging.info(
                f"[{i}/{len(pdf_files)}] Processing PDF: {os.path.basename(pdf_path)}"
            )
            csv_file = self.process_pdf(pdf_path, output_dir)
            if csv_file:
                csv_files.append(csv_file)

        return csv_files

    def _process_page(
        self, page, pdf_path: str, page_num: int
    ) -> Optional[ProcessingResult]:
        """Process a single page from a PDF document."""
        try:
            logging.info(f"Processing page {page_num} of {pdf_path}")

            # Convert page to image
            pix = page.get_pixmap()
            img_data = pix.tobytes("png")

            # Convert to base64
            img_base64 = base64.b64encode(img_data).decode("utf-8")

            # Extract transactions using vision API
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self.EXTRACTION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_base64}"},
                        },
                    ],
                }
            ]

            response = self.client.chat.completions.create(
                model=self.MODEL_NAME,
                messages=messages,
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
            )

            # Parse response
            try:
                content = response.choices[0].message.content
                transactions = self._parse_transactions(content, pdf_path, page_num)
                logging.info(
                    f"Successfully extracted {len(transactions)} transactions from page {page_num}"
                )
                return ProcessingResult(
                    success=True, extracted_transactions=transactions, error=None
                )
            except Exception as e:
                logging.error(f"Failed to parse transactions from page {page_num}: {e}")
                return ProcessingResult(
                    success=False, extracted_transactions=[], error=str(e)
                )

        except Exception as e:
            logging.error(f"Error processing page {page_num}: {e}")
            return ProcessingResult(
                success=False, extracted_transactions=[], error=str(e)
            )

    def _parse_transactions(
        self, content: str, source_file: str, page_number: int
    ) -> List[Transaction]:
        """Parse the API response content into Transaction objects.

        Args:
            content: The raw API response content
            source_file: The source PDF file path
            page_number: The page number in the PDF

        Returns:
            List of Transaction objects
        """
        transactions_data = json.loads(content)
        transactions = []

        for t in transactions_data:
            transaction = Transaction(
                date=t["date"],
                description=t["description"],
                amount=float(t["amount"]),
                category=t["category"],
                source_file=source_file,
                page_number=page_number,
                extracted_at=datetime.now(),
            )
            transactions.append(transaction)

        return transactions
