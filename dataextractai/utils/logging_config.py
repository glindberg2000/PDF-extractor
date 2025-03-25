import logging
import sys


def configure_logging():
    """
    Configure logging for the application.
    Reduces verbose output from libraries like PDFMiner.
    """
    # Set root logger to INFO
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    # Set PDFMiner to WARNING level to reduce debug output
    logging.getLogger("pdfminer").setLevel(logging.WARNING)

    # Keep our own loggers at INFO
    logging.getLogger("dataextractai").setLevel(logging.INFO)

    # Set First Republic Bank parser to DEBUG for troubleshooting
    logging.getLogger("dataextractai.parsers.first_republic_bank_parser").setLevel(
        logging.DEBUG
    )

    # Return logger for module use if needed
    return logging.getLogger(__name__)
