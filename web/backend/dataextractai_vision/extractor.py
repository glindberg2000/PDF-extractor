"""
PDF Transaction Extractor
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from .parser_system import process_pdf, Transaction

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a PDF file."""

    transactions: List[Transaction]
    pages_processed: int
    total_pages: int
    processing_details: List[str]
    error_message: Optional[str] = None


def process_pdf_file(pdf_path: str) -> ProcessingResult:
    """Process a PDF file and extract transactions."""
    try:
        # Extract transactions using the parser system
        transactions = process_pdf(pdf_path)

        # Get total pages
        import fitz

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        doc.close()

        # Create processing details
        processing_details = [
            f"Successfully processed {len(transactions)} transactions",
            f"Processed all {total_pages} pages",
        ]

        return ProcessingResult(
            transactions=transactions,
            pages_processed=total_pages,
            total_pages=total_pages,
            processing_details=processing_details,
        )

    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {e}")
        return ProcessingResult(
            transactions=[],
            pages_processed=0,
            total_pages=0,
            processing_details=[f"Error: {str(e)}"],
            error_message=str(e),
        )


def extract_from_image(
    image_path: str, source_file: str, page_number: int
) -> List[Transaction]:
    """Extract transactions from an image."""
    # For now, we don't support image-based extraction
    # This could be implemented later using OCR if needed
    raise NotImplementedError("Image-based extraction is not supported")
