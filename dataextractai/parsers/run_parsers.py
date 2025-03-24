"""
run_parsers.py

This script is designed to sequentially execute a series of parser functions
for different types of financial documents. Each parser is responsible for
extracting transaction data from a specific format of PDF file and outputting
the results to a designated CSV and XLSX file.

The script assumes that each parser module has a `run` function that takes
no arguments and returns a pandas DataFrame containing the parsed data.
The script also assumes that the parsers write their output to the filesystem.

The script operates on the assumption that it is being run from the root
directory of the project, where the 'dataextractai' package can be found.
It also assumes that the required input files are located within the 'data/input'
directory, categorized into subdirectories by parser type (e.g., 'amazon', 'bofa_bank').

The output CSV and XLSX files are written to the 'data/output' directory,
following the same categorization as the input files.

Usage:
    To run all parsers and output to CSV and XLSX files:
    $ python  dataextractai/parsers/run_parsers.py

    To import and run parsers within another module:
    from scripts.run_parsers import run_all_parsers
    run_all_parsers()

The script's function is to streamline the process of running all parsers
and to ensure that the extracted data is saved in a consistent and
organized manner. This automation aids in maintaining a standardized
data processing pipeline.

Author: Gregory Lindberg
Date: November 5, 2023
"""

import os
import pandas as pd
from datetime import datetime  # Import the datetime class from the datetime module
from rich.progress import Progress
from rich.console import Console
import glob

# Configure logging to reduce PDFMiner debug output
from dataextractai.utils.logging_config import configure_logging

configure_logging()

# Initialize console for rich output
console = Console()

# Import config functions
from dataextractai.utils.config import (
    get_client_config,
    update_config_for_client,
    get_current_paths,
)

# Import the parser functions
from dataextractai.parsers.wellsfargo_bank_parser import (
    run as run_wells_fargo_bank_parser,
)
from dataextractai.parsers.wellsfargo_mastercard_parser import (
    run as run_wells_fargo_mastercard_parser,
)
from dataextractai.parsers.wellsfargo_bank_csv_parser import (
    run as run_wells_fargo_bank_csv_parser,
)
from dataextractai.parsers.wellsfargo_visa_parser import (
    run as run_wells_fargo_visa_parser,
)
from dataextractai.parsers.amazon_parser import run as run_amazon_parser
from dataextractai.parsers.bofa_bank_parser import run as run_bofa_bank_parser
from dataextractai.parsers.bofa_visa_parser import run as run_bofa_visa_parser
from dataextractai.parsers.chase_visa_parser import run as run_chase_visa_parser
from dataextractai.parsers.first_republic_bank_parser import (
    run as run_first_republic_bank_parser,
)

# Map parser names to their functions
PARSER_FUNCTIONS = {
    "amazon": run_amazon_parser,
    "bofa_bank": run_bofa_bank_parser,
    "bofa_visa": run_bofa_visa_parser,
    "chase_visa": run_chase_visa_parser,
    "wellsfargo_bank": run_wells_fargo_bank_parser,
    "wellsfargo_mastercard": run_wells_fargo_mastercard_parser,
    "wellsfargo_bank_csv": run_wells_fargo_bank_csv_parser,
    "wellsfargo_visa": run_wells_fargo_visa_parser,
    "first_republic_bank": run_first_republic_bank_parser,
}

# Add the data transformation function here
from dataextractai.utils.data_transformation import (
    apply_transformation_map as transform_to_core_structure,
)


def parse_date(date_str):
    """
    Parse a date string into a datetime object, handling different date formats.
    """
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):  # Add more formats here if needed
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            pass
    raise ValueError(f"Unknown date format: {date_str}")


def has_files_to_parse(directory):
    """
    Check if the specified directory exists and contains any files.

    Args:
        directory (str): Path to the directory to check

    Returns:
        bool: True if directory exists and contains files, False otherwise
    """
    if not os.path.exists(directory):
        print(f"Directory does not exist: {directory}")
        return False

    files = [
        f
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and not f.startswith(".")  # Ignore hidden files
    ]
    if not files:
        print(f"No files found in directory: {directory}")
        return False

    return True


def run_all_parsers(client_name: str, config: dict) -> int:
    """Run all parsers for a client.

    Args:
        client_name: Name of the client
        config: Client configuration dictionary

    Returns:
        int: Total number of transactions processed
    """
    # Get current paths for this client
    paths = get_current_paths(config)
    input_dirs = paths["input_dirs"]
    output_paths = paths["output_paths"]

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_paths["amazon"]["csv"])
    os.makedirs(output_dir, exist_ok=True)

    # Print input directories for debug
    print(f"Client: {client_name}")
    print(f"Output directory: {output_dir}")

    total_processed = 0

    with Progress() as progress:
        task = progress.add_task("Processing documents...", total=len(PARSER_FUNCTIONS))

        for parser_name, parser_func in PARSER_FUNCTIONS.items():
            input_dir = input_dirs[parser_name]

            # Make sure the directory exists
            if not os.path.exists(input_dir):
                progress.print(f"No input directory found for {parser_name}")
                progress.advance(task)
                continue

            # Get PDF files directly using glob
            pdf_files = glob.glob(os.path.join(input_dir, "*.pdf"))
            if not pdf_files:
                progress.print(f"No PDF files found in {input_dir}")
                progress.advance(task)
                continue

            progress.print(
                f"Found {len(pdf_files)} PDF files in {parser_name} directory"
            )

            # These parsers process all files in a directory at once
            # rather than individual files
            directory_based_parsers = [
                "wellsfargo_visa",
                "wellsfargo_bank",
                "first_republic_bank",
                "wellsfargo_bank_csv",
            ]

            # Process directory-based parsers all at once
            if parser_name in directory_based_parsers and pdf_files:
                try:
                    progress.print(
                        f"Processing all files in {parser_name} directory..."
                    )

                    # Ensure the parser uses the correct directory path
                    if parser_name == "first_republic_bank":
                        # First Republic Bank parser needs to have its SOURCE_DIR monkey-patched
                        import dataextractai.parsers.first_republic_bank_parser as frb_parser

                        # Save the original value to restore later
                        original_source_dir = frb_parser.SOURCE_DIR
                        original_output_csv = frb_parser.OUTPUT_PATH_CSV
                        original_output_xlsx = frb_parser.OUTPUT_PATH_XLSX

                        # Set the new values for client-specific paths
                        frb_parser.SOURCE_DIR = input_dir
                        frb_parser.OUTPUT_PATH_CSV = output_paths[parser_name]["csv"]
                        frb_parser.OUTPUT_PATH_XLSX = output_paths[parser_name]["xlsx"]

                        # Now run the parser with all the parameters
                        df = frb_parser.run(
                            source_dir=input_dir,
                            output_path_csv=output_paths[parser_name]["csv"],
                            output_path_xlsx=output_paths[parser_name]["xlsx"],
                            write_to_file=False,
                        )

                        # Restore the original values
                        frb_parser.SOURCE_DIR = original_source_dir
                        frb_parser.OUTPUT_PATH_CSV = original_output_csv
                        frb_parser.OUTPUT_PATH_XLSX = original_output_xlsx
                    elif parser_name == "wellsfargo_visa":
                        # Wells Fargo Visa parser needs to have its SOURCE_DIR monkey-patched
                        import dataextractai.parsers.wellsfargo_visa_parser as wfv_parser

                        # Save the original value to restore later
                        original_source_dir = wfv_parser.SOURCE_DIR
                        # Set the new value to our client-specific input directory
                        wfv_parser.SOURCE_DIR = input_dir

                        # Now run the parser
                        df = parser_func(write_to_file=False)

                        # Restore the original value
                        wfv_parser.SOURCE_DIR = original_source_dir
                    elif parser_name == "wellsfargo_bank_csv":
                        # Wells Fargo Bank CSV parser needs to have its SOURCE_DIR monkey-patched
                        import dataextractai.parsers.wellsfargo_bank_csv_parser as wfbc_parser

                        # Save the original value to restore later
                        original_source_dir = wfbc_parser.SOURCE_DIR
                        # Set the new value to our client-specific input directory
                        wfbc_parser.SOURCE_DIR = input_dir

                        # Now run the parser
                        df = parser_func(write_to_file=False)

                        # Restore the original value
                        wfbc_parser.SOURCE_DIR = original_source_dir
                    else:
                        # For other directory-based parsers, we need a different approach
                        # Patch the source directory in the config
                        from ..utils import config

                        original_dir = config.PARSER_INPUT_DIRS[parser_name]
                        # Set to our client-specific input directory
                        config.PARSER_INPUT_DIRS[parser_name] = input_dir

                        # Run the parser
                        df = parser_func(write_to_file=False)

                        # Restore the original config
                        config.PARSER_INPUT_DIRS[parser_name] = original_dir

                    if df is not None and not df.empty:
                        # Save to CSV
                        csv_path = output_paths[parser_name]["csv"]
                        df.to_csv(csv_path, index=False)
                        progress.print(f"Saved CSV output to {csv_path}")

                        # Save to Excel if xlsx path exists
                        if "xlsx" in output_paths[parser_name]:
                            xlsx_path = output_paths[parser_name]["xlsx"]
                            df.to_excel(xlsx_path, index=False)
                            progress.print(f"Saved Excel output to {xlsx_path}")

                        total_processed += len(df)
                        progress.print(
                            f"Successfully processed {parser_name} directory with {len(df)} transactions"
                        )
                    else:
                        progress.print(
                            f"No data extracted from {parser_name} directory"
                        )

                except Exception as e:
                    progress.print(
                        f"Error processing {parser_name} directory: {str(e)}"
                    )

                progress.advance(task)
                continue

            # Special handling for Wells Fargo Bank CSV files
            elif parser_name == "wellsfargo_bank_csv":
                try:
                    # Look for actual CSV files, not just PDFs
                    csv_files = glob.glob(os.path.join(input_dir, "*.csv"))
                    if not csv_files:
                        progress.print(f"No CSV files found in {input_dir}")
                        progress.advance(task)
                        continue

                    progress.print(
                        f"Found {len(csv_files)} CSV files in {parser_name} directory"
                    )

                    # Import and modify the module
                    import dataextractai.parsers.wellsfargo_bank_csv_parser as wfbc_parser

                    # Save original values
                    original_source_dir = wfbc_parser.SOURCE_DIR
                    original_output_csv = wfbc_parser.OUTPUT_PATH_CSV
                    original_output_xlsx = wfbc_parser.OUTPUT_PATH_XLSX

                    # Set new values
                    wfbc_parser.SOURCE_DIR = input_dir
                    wfbc_parser.OUTPUT_PATH_CSV = output_paths[parser_name]["csv"]
                    wfbc_parser.OUTPUT_PATH_XLSX = output_paths[parser_name]["xlsx"]

                    # Run parser
                    df = parser_func(write_to_file=True)  # Let it write directly

                    # Restore original values
                    wfbc_parser.SOURCE_DIR = original_source_dir
                    wfbc_parser.OUTPUT_PATH_CSV = original_output_csv
                    wfbc_parser.OUTPUT_PATH_XLSX = original_output_xlsx

                    if df is not None and not df.empty:
                        total_processed += len(df)
                        progress.print(
                            f"Successfully processed {parser_name} directory with {len(df)} transactions"
                        )
                    else:
                        progress.print(
                            f"No data extracted from {parser_name} directory"
                        )

                except Exception as e:
                    progress.print(
                        f"Error processing {parser_name} directory: {str(e)}"
                    )

                progress.advance(task)
                continue

            # Process each PDF file individually for file-based parsers
            for pdf_path in pdf_files:
                try:
                    pdf_filename = os.path.basename(pdf_path)
                    progress.print(f"Processing {pdf_filename}...")

                    # Custom handling for different parser types
                    if parser_name == "chase_visa":
                        # Chase Visa parser expects a directory, not a file
                        try:
                            from dataextractai.parsers.chase_visa_parser import (
                                main as chase_main,
                            )

                            pdf_dir = os.path.dirname(pdf_path)
                            df = chase_main(
                                write_to_file=False,
                                source_dir=pdf_dir,  # Pass the directory
                                output_csv=output_paths[parser_name]["csv"],
                                output_xlsx=output_paths[parser_name]["xlsx"],
                            )
                        except Exception as e:
                            progress.print(f"Error with chase_visa parser: {str(e)}")
                            continue

                    elif parser_name == "amazon":
                        # Amazon parser has its own way of accessing files
                        try:
                            # Import without running
                            import dataextractai.parsers.amazon_parser as amazon_parser

                            # Save original value
                            original_source_dir = amazon_parser.SOURCE_DIR
                            # Set to our directory
                            amazon_parser.SOURCE_DIR = os.path.dirname(pdf_path)

                            # Run parser function
                            df = parser_func(write_to_file=False)

                            # Restore original
                            amazon_parser.SOURCE_DIR = original_source_dir

                        except Exception as e:
                            progress.print(f"Error with amazon parser: {str(e)}")
                            continue

                    elif parser_name == "wellsfargo_bank_csv":
                        # This parser accepts file paths directly
                        df = parser_func(
                            input_dir=pdf_path, output_paths=output_paths[parser_name]
                        )

                    elif parser_name in ["bofa_bank", "bofa_visa"]:
                        # BofA parsers
                        try:
                            # Import the right module
                            if parser_name == "bofa_bank":
                                import dataextractai.parsers.bofa_bank_parser as bofa_parser
                            else:
                                import dataextractai.parsers.bofa_visa_parser as bofa_parser

                            # Save original
                            original_source_dir = bofa_parser.SOURCE_DIR
                            # Set to our directory with this specific file
                            bofa_parser.SOURCE_DIR = os.path.dirname(pdf_path)
                            # We also need to keep track of just the filename
                            bofa_parser.CURRENT_FILE = os.path.basename(pdf_path)

                            # Run parser
                            df = parser_func(write_to_file=False)

                            # Restore original
                            bofa_parser.SOURCE_DIR = original_source_dir
                            if hasattr(bofa_parser, "CURRENT_FILE"):
                                del bofa_parser.CURRENT_FILE

                        except Exception as e:
                            progress.print(f"Error with {parser_name} parser: {str(e)}")
                            continue

                    else:
                        # Generic approach for other parsers
                        try:
                            # Process all files in the directory
                            df = parser_func(write_to_file=False)
                        except Exception as e:
                            progress.print(f"Directory processing failed: {str(e)}")
                            continue

                    if df is not None and not df.empty:
                        # Save to CSV
                        csv_path = output_paths[parser_name]["csv"]
                        df.to_csv(csv_path, index=False)
                        progress.print(f"Saved CSV output to {csv_path}")

                        # Save to Excel if xlsx path exists
                        if "xlsx" in output_paths[parser_name]:
                            xlsx_path = output_paths[parser_name]["xlsx"]
                            df.to_excel(xlsx_path, index=False)
                            progress.print(f"Saved Excel output to {xlsx_path}")

                        total_processed += len(df)
                        progress.print(
                            f"Successfully processed {pdf_filename} with {len(df)} transactions"
                        )
                    else:
                        progress.print(f"No data extracted from {pdf_filename}")

                except Exception as e:
                    progress.print(f"Error processing {pdf_path}: {str(e)}")

            progress.advance(task)

    return total_processed


if __name__ == "__main__":
    # When run directly, we'll ask for a client name
    import sys

    if len(sys.argv) > 1:
        client_name = sys.argv[1]
        # Get client config
        from dataextractai.utils.config import get_client_config

        config = get_client_config(client_name)

        # Ensure client_name is in the config
        config["client_name"] = client_name

        # Run the parsers
        total_processed = run_all_parsers(client_name, config)
        print(f"Total transactions processed: {total_processed}")
    else:
        print("Error: Please provide a client name")
        print("Usage: python -m dataextractai.parsers.run_parsers <client_name>")
        sys.exit(1)
