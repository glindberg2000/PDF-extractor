"""
Parser module for extracting transaction data from various financial document formats.
"""

# Import the logging configuration
from dataextractai.utils.logging_config import configure_logging

configure_logging()

# Import parsers for direct access
from .amazon_parser import run as run_amazon_parser
from .bofa_bank_parser import run as run_bofa_bank_parser
from .bofa_visa_parser import run as run_bofa_visa_parser
from .chase_visa_parser import run as run_chase_visa_parser
from .wellsfargo_bank_parser import run as run_wells_fargo_bank_parser
from .wellsfargo_mastercard_parser import run as run_wells_fargo_mastercard_parser
from .wellsfargo_visa_parser import run as run_wells_fargo_visa_parser
from .wellsfargo_bank_csv_parser import run as run_wells_fargo_bank_csv_parser
from .first_republic_bank_parser import run as run_first_republic_bank_parser

# Create a version of run_parsers that can be imported
from .run_parsers import run_all_parsers

