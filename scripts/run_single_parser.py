#!/usr/bin/env python3
import argparse
import os
import sys
from pprint import pprint

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_root)

# Import the main entrypoints for each modular parser
from dataextractai.parsers.amazon_invoice_pdf_parser import main as amazon_invoice_main
from dataextractai.parsers.amazon_pdf_parser import main as amazon_pdf_main
from dataextractai.parsers.apple_card_csv_parser import main as apple_main
from dataextractai.parsers.capitalone_csv_parser import main as capitalone_csv_main
from dataextractai.parsers.chase_visa_csv_parser import main as chase_visa_csv_main
from dataextractai.parsers.first_republic_bank_parser import main as frb_main
from dataextractai.parsers.wellsfargo_bank_csv_parser import main as wf_bank_csv_main
from dataextractai.parsers.wellsfargo_visa_parser import main as wf_visa_main
from dataextractai.parsers.bofa_bank_parser import main as bofa_bank_main
from dataextractai.parsers.bofa_visa_parser import main as bofa_visa_main
from dataextractai.parsers.capitalone_visa_print_parser import (
    main as capitalone_visa_print_main,
)
from dataextractai.parsers.chase_checking import main as chase_checking_main
from dataextractai.parsers.chase_visa_parser import main as chase_visa_main
from dataextractai.parsers.wellsfargo_bank_parser import main as wf_bank_main
from dataextractai.parsers.wellsfargo_checking_csv_parser import (
    main as wf_checking_csv_main,
)
from dataextractai.parsers.wellsfargo_mastercard_parser import (
    main as wf_mastercard_main,
)


PARSER_MAP = {
    "amazon_invoice": amazon_invoice_main,
    "amazon_pdf": amazon_pdf_main,
    "amazon": amazon_invoice_main,  # Default for 'amazon' keyword
    "apple_card": apple_main,
    "capitalone_csv": capitalone_csv_main,
    "capitalone_visa_print": capitalone_visa_print_main,
    "chase_visa_csv": chase_visa_csv_main,
    "chase_visa": chase_visa_main,
    "chase_checking": chase_checking_main,
    "first_republic": frb_main,
    "bofa_bank": bofa_bank_main,
    "bofa_visa": bofa_visa_main,
    "wellsfargo_bank_csv": wf_bank_csv_main,
    "wellsfargo_bank": wf_bank_main,
    "wellsfargo_checking_csv": wf_checking_csv_main,
    "wellsfargo_visa": wf_visa_main,
    "wellsfargo_mastercard": wf_mastercard_main,
}


def main():
    """Run a single modular parser on a file."""
    parser = argparse.ArgumentParser(
        description="Run a single modular parser on a file."
    )
    parser.add_argument("file_path", help="The path to the file to parse.")
    parser.add_argument(
        "--parser",
        help="The name of the parser to use (e.g., 'amazon_invoice'). If not provided, it will be inferred from the filename.",
    )
    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        print(f"Error: File not found at {args.file_path}")
        sys.exit(1)

    parser_to_use = None
    parser_name = "unknown"
    if args.parser:
        if args.parser in PARSER_MAP:
            parser_to_use = PARSER_MAP[args.parser]
            parser_name = args.parser
        else:
            print(f"Error: Parser '{args.parser}' not found.")
            print(f"Available parsers: {', '.join(PARSER_MAP.keys())}")
            sys.exit(1)
    else:
        filename = os.path.basename(args.file_path).lower()
        # Sort by key length to match more specific keywords first
        sorted_keywords = sorted(PARSER_MAP.keys(), key=len, reverse=True)
        for keyword in sorted_keywords:
            # remove underscores for better matching
            if keyword.replace("_", "") in filename.replace("_", ""):
                parser_to_use = PARSER_MAP[keyword]
                parser_name = keyword
                print(f"Inferred parser: '{parser_name}'")
                break

    if not parser_to_use:
        print(
            "Error: Could not infer parser from filename. Please specify with --parser."
        )
        print(f"Available parsers: {', '.join(PARSER_MAP.keys())}")
        sys.exit(1)

    print(f"Running parser on: {args.file_path}")
    output = parser_to_use(args.file_path)

    print("\n--- Parser Output ---")
    # Use pprint for a more readable output of the dictionary
    pprint(output.dict())
    print("---------------------\n")
    print(f"Successfully ran parser '{parser_name}' on '{args.file_path}'.")


if __name__ == "__main__":
    main()
