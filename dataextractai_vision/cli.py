"""
Command-line interface for the vision-based PDF transaction extractor.
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional

from .extractor import VisionExtractor


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract transactions from PDF statements using GPT-4 Vision",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Process a single PDF file
    %(prog)s process-file path/to/statement.pdf
    
    # Process all PDFs in a directory
    %(prog)s process-dir path/to/statements/
    
    # Process with custom output directory
    %(prog)s process-dir path/to/statements/ --output path/to/output/
    
    # Force reprocessing of already processed files
    %(prog)s process-dir path/to/statements/ --force
        """,
    )

    # Common arguments that will be added to both subparsers
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force reprocessing of already processed files",
    )
    common_parser.add_argument(
        "--log-file",
        help="Path to log file (default: extraction.log)",
        default="extraction.log",
    )
    common_parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level",
    )
    common_parser.add_argument(
        "--history-db",
        help="Path to processing history database (default: processing_history.db)",
        default="processing_history.db",
    )
    common_parser.add_argument(
        "--output",
        "-o",
        help="Output directory (optional)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Process single file
    file_parser = subparsers.add_parser(
        "process-file", help="Process a single PDF file", parents=[common_parser]
    )
    file_parser.add_argument("pdf_path", help="Path to the PDF file")

    # Process directory
    dir_parser = subparsers.add_parser(
        "process-dir", help="Process all PDFs in a directory", parents=[common_parser]
    )
    dir_parser.add_argument("input_dir", help="Directory containing PDF files")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    return args


def process_file(
    extractor: VisionExtractor, pdf_path: str, output_dir: Optional[str] = None
) -> Optional[str]:
    """Process a single PDF file."""
    try:
        csv_file = extractor.process_pdf(pdf_path, output_dir)
        return csv_file
    except Exception as e:
        logging.error(f"Error processing file {pdf_path}: {str(e)}")
        return None


def process_directory(
    extractor: VisionExtractor, input_dir: str, output_dir: Optional[str] = None
) -> list[str]:
    """Process all PDFs in a directory."""
    try:
        csv_files = extractor.process_directory(input_dir, output_dir)
        return csv_files
    except Exception as e:
        logging.error(f"Error processing directory {input_dir}: {str(e)}")
        return []


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        handlers=[logging.FileHandler(args.log_file), logging.StreamHandler()],
    )

    try:
        extractor = VisionExtractor(force_reprocess=args.force)
    except ValueError as e:
        logging.error(f"Error: {e}")
        logging.error("Please set the OPENAI_API_KEY environment variable")
        sys.exit(1)

    # Process based on command
    if args.command == "process-file":
        input_path = Path(args.pdf_path)
        if not input_path.suffix.lower() == ".pdf":
            logging.error(f"Input file must be a PDF: {input_path}")
            sys.exit(1)
        csv_file = process_file(extractor, str(input_path), args.output)
        if csv_file:
            logging.info(f"Successfully processed {input_path}")
            logging.info(f"Output saved to: {csv_file}")
            sys.exit(0)
        else:
            logging.error("Failed to process file")
            sys.exit(1)
    else:  # process-dir
        input_path = Path(args.input_dir)
        if not input_path.is_dir():
            logging.error(f"Input must be a directory: {input_path}")
            sys.exit(1)

        csv_files = process_directory(extractor, str(input_path), args.output)
        if csv_files:
            logging.info(f"\nSuccessfully processed {len(csv_files)} files:")
            for csv_file in csv_files:
                logging.info(f"- {csv_file}")
            sys.exit(0)
        else:
            logging.warning("No files were processed")
            sys.exit(1)


def run() -> None:
    """Entry point for the CLI."""
    try:
        main()
    except KeyboardInterrupt:
        logging.info("\nProcessing interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Unexpected error: {str(e)}")
        sys.exit(1)
