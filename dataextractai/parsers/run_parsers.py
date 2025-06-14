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
from dataextractai.parsers_core.registry import ParserRegistry

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


def run_all_parsers(
    client_name: str, config: dict, dump_per_statement_raw=False
) -> int:
    """Run all parsers for a client.

    Args:
        client_name: Name of the client
        config: Client configuration dictionary
        dump_per_statement_raw: Flag to dump raw extracted data for each statement file

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

    if dump_per_statement_raw:
        # Always create raw_per_statement inside the client/output dir
        raw_dir = os.path.join(output_dir, "raw_per_statement")
        os.makedirs(raw_dir, exist_ok=True)
        print(f"[DEBUG] Per-statement raw output directory: {raw_dir}")

    # Print input directories for debug
    print(f"Client: {client_name}")
    print(f"Output directory: {output_dir}")

    total_processed = 0

    with Progress() as progress:
        task = progress.add_task("Processing documents...", total=len(PARSER_FUNCTIONS))

        for parser_name, parser_func in PARSER_FUNCTIONS.items():
            input_dir = input_dirs[parser_name]
            print(f"[DEBUG] Checking input directory for {parser_name}: {input_dir}")
            if not os.path.exists(input_dir):
                print(
                    f"[DEBUG] Directory does not exist for {parser_name}: {input_dir}"
                )
                progress.print(f"No input directory found for {parser_name}")
                progress.advance(task)
                continue
            files_in_dir = os.listdir(input_dir)
            print(f"[DEBUG] Files in {input_dir}: {files_in_dir}")
            # Get PDF and CSV files
            pdf_files = glob.glob(os.path.join(input_dir, "*.pdf"))
            csv_files = glob.glob(os.path.join(input_dir, "*.csv"))
            if not pdf_files and not csv_files:
                print(f"[DEBUG] No PDF or CSV files found in {input_dir}")
                progress.print(f"No PDF or CSV files found in {input_dir}")
                progress.advance(task)
                continue

            progress.print(
                f"Found {len(pdf_files)} PDF and {len(csv_files)} CSV files in {parser_name} directory"
            )

            # Directory-based parsers
            directory_based_parsers = [
                "wellsfargo_visa",
                "wellsfargo_bank",
                "first_republic_bank",
            ]

            # If parser is directory-based, process as before
            if parser_name in directory_based_parsers:
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

                    if dump_per_statement_raw:
                        # After processing, if dump_per_statement_raw, dump the full DataFrame
                        out_path = os.path.join(raw_dir, f"{parser_name}_all.raw.csv")
                        df.to_csv(out_path, index=False)
                        print(f"[DEBUG] Saved directory-based raw data to {out_path}")

                except Exception as e:
                    progress.print(
                        f"Error processing {parser_name} directory: {str(e)}"
                    )

                progress.advance(task)
                continue

            # For file-based parsers, process each file individually
            for file_path in pdf_files + csv_files:
                try:
                    file_ext = os.path.splitext(file_path)[1].lower()
                    file_dir = os.path.dirname(file_path)
                    file_base = os.path.splitext(os.path.basename(file_path))[0]
                    # Import the parser's main function dynamically
                    parser_module = __import__(
                        f"dataextractai.parsers.{parser_name}_parser", fromlist=["main"]
                    )
                    main_func = getattr(parser_module, "main", None)
                    if main_func is None:
                        print(
                            f"[DEBUG] No main() in {parser_name}_parser, skipping raw dump for {file_path}"
                        )
                        continue
                    # Call main for this file only
                    if file_ext == ".pdf":
                        df_raw = main_func(write_to_file=False, source_dir=file_dir)
                    elif file_ext == ".csv":
                        df_raw = main_func(write_to_file=False, source_dir=file_dir)
                    else:
                        print(
                            f"[DEBUG] Unsupported file type for raw dump: {file_path}"
                        )
                        continue
                    # Filter to just this file if possible
                    if df_raw is not None and not df_raw.empty:
                        # Try to filter by file_path or similar column
                        if "file_path" in df_raw.columns:
                            df_raw = df_raw[
                                df_raw["file_path"].str.contains(file_base, na=False)
                            ]
                        out_path = os.path.join(raw_dir, f"{file_base}.raw.csv")
                        df_raw.to_csv(out_path, index=False)
                        print(f"[DEBUG] Saved raw data to {out_path}")
                except Exception as e:
                    print(f"[DEBUG] Error dumping raw data for {file_path}: {e}")
            progress.advance(task)

    return total_processed


run_parsers = run_all_parsers


def detect_parsers_in_folder(folder_path):
    """
    Detects the parser type for each file in the folder using batch_detect_parsers.
    Prints a DataFrame with file paths and detected parser types.
    """
    files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(".pdf") or f.lower().endswith(".csv")
    ]
    results = ParserRegistry.batch_detect_parsers(files)
    df = pd.DataFrame(list(results.items()), columns=["file_path", "detected_parser"])
    print(df)
    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run all parsers or detect parser types in a folder."
    )
    parser.add_argument(
        "--detect-folder", type=str, help="Folder path to batch detect parser types."
    )
    # ... existing CLI args ...
    args = parser.parse_args()

    if args.detect_folder:
        detect_parsers_in_folder(args.detect_folder)
    # ... existing CLI logic ...
