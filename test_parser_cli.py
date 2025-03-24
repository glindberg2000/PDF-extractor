#!/usr/bin/env python3
"""
Test script to verify the parser CLI integration.
This helps debug the parser path handling and configuration.
"""

import os
import sys
from pathlib import Path
import click
import subprocess
import re


def ensure_directory(path):
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)


def create_test_pdf(output_path):
    """Create a simple test PDF file."""
    try:
        # Create a simple test PDF file
        import io
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        # Create a buffer and PDF document
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)

        # Add some content
        pdf.setFont("Helvetica", 12)
        pdf.drawString(100, 750, f"Test PDF for parser")
        pdf.drawString(100, 730, f"Output path: {output_path}")
        pdf.drawString(100, 710, f"Date: {__import__('time').strftime('%Y-%m-%d')}")
        pdf.drawString(100, 690, "This is a test file for parser debugging.")
        pdf.drawString(
            100, 670, "In a real application, you would place actual bank statements or"
        )
        pdf.drawString(
            100, 650, "other financial documents in these input directories."
        )

        # Save the PDF
        pdf.save()

        # Write the buffer content to a file
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())

        return True
    except Exception as e:
        click.echo(f"Error creating test PDF: {str(e)}")
        return False


def setup_test_client(client_name="test_client"):
    """Set up a test client with all necessary directories and files."""
    # Create client directory
    client_dir = os.path.join("data", "clients", client_name)
    input_dir = os.path.join(client_dir, "input")
    output_dir = os.path.join(client_dir, "output")

    # Ensure directories exist
    ensure_directory(input_dir)
    ensure_directory(output_dir)

    # Create parser directories
    parser_dirs = [
        "amazon",
        "bofa_bank",
        "bofa_visa",
        "chase_visa",
        "wellsfargo_bank",
        "wellsfargo_mastercard",
        "wellsfargo_visa",
        "wellsfargo_bank_csv",
        "first_republic_bank",
    ]

    # Create each parser directory and a test PDF in it
    for parser in parser_dirs:
        parser_dir = os.path.join(input_dir, parser)
        ensure_directory(parser_dir)
        pdf_path = os.path.join(parser_dir, f"test_{parser}.pdf")
        create_test_pdf(pdf_path)
        click.echo(f"Created test PDF in {parser_dir}")

    # Create a client config file
    config_path = os.path.join(client_dir, "client_config.yaml")
    import yaml

    config = {
        "client_name": client_name,
        "business_type": "Test Business",
        "industry": "Software Testing",
        "location": "Test Location",
        "annual_revenue": "100000",
        "employee_count": 5,
        "business_activities": ["Testing", "Debugging"],
        "typical_expenses": ["Software", "Hardware"],
        "last_updated": __import__("datetime").datetime.now().isoformat(),
    }

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    click.echo(f"Created client config at {config_path}")

    return client_name


def run_parser_test(client_name):
    print(f"\nRunning parser test:")
    print(f"\nRunning parser for client {client_name}...")

    # Create symlink to client data for easier access
    client_dir = os.path.join("data", "clients", client_name)
    symlink_dir = os.path.join("dataextractai", "data", "clients", client_name)

    # Create symlink if it doesn't exist
    if not os.path.exists(symlink_dir):
        os.makedirs(os.path.dirname(symlink_dir), exist_ok=True)
        try:
            # For Windows compatibility, use a different approach
            if os.name == "nt":
                # Use directory junction on Windows
                subprocess.run(
                    ["mklink", "/J", symlink_dir, client_dir], shell=True, check=True
                )
            else:
                os.symlink(os.path.abspath(client_dir), symlink_dir)
            print(f"Created symlink to client data at: {symlink_dir}")
        except Exception as e:
            print(f"Warning: Could not create symlink: {e}")

    print("\nRunning parsers for PDFs in client directory...")
    try:
        # Pass the full client name to the parser
        subprocess.run(
            ["python", "-m", "dataextractai.parsers.run_parsers", client_name],
            check=True,
        )

        # Find the output directory
        output_dir = find_output_dir(client_name)

        # Print a summary of the parser results
        print_parser_summary(output_dir)

    except subprocess.CalledProcessError as e:
        print(f"\nParser failed to run.")
        print(e.stdout.decode("utf-8") if e.stdout else "")
        print(e.stderr.decode("utf-8") if e.stderr else "")


def extract_parser_summary(output):
    """Extract information about which parsers were run from the parser output."""
    summary = {}

    # Regular expressions to match various patterns in the output
    found_files_pattern = re.compile(
        r"Found (\d+) (?:PDF|CSV) files in (\w+) directory"
    )
    success_pattern = re.compile(
        r"Successfully processed (\w+) directory with (\d+) transactions"
    )
    no_data_pattern = re.compile(r"No data extracted from (\w+) directory")
    error_pattern = re.compile(
        r"Error (?:with|processing) (\w+)(?:_| )(?:parser|directory)"
    )

    for line in output.split("\n"):
        # Match files found
        files_match = found_files_pattern.search(line)
        if files_match:
            file_count = int(files_match.group(1))
            parser_name = files_match.group(2)

            if parser_name not in summary:
                summary[parser_name] = {
                    "files": file_count,
                    "transactions": 0,
                    "status": "Found files",
                }
            else:
                summary[parser_name]["files"] = file_count

        # Match successful processing
        success_match = success_pattern.search(line)
        if success_match:
            parser_name = success_match.group(1)
            transaction_count = int(success_match.group(2))

            if parser_name not in summary:
                summary[parser_name] = {
                    "files": 0,
                    "transactions": transaction_count,
                    "status": "Success",
                }
            else:
                summary[parser_name]["transactions"] = transaction_count
                summary[parser_name]["status"] = "Success"

        # Match no data extracted
        no_data_match = no_data_pattern.search(line)
        if no_data_match:
            parser_name = no_data_match.group(1)

            if parser_name not in summary:
                summary[parser_name] = {
                    "files": 0,
                    "transactions": 0,
                    "status": "No data found",
                }
            else:
                summary[parser_name]["status"] = "No data found"

        # Match errors
        error_match = error_pattern.search(line)
        if error_match:
            parser_name = error_match.group(1)

            if parser_name not in summary:
                summary[parser_name] = {
                    "files": 0,
                    "transactions": 0,
                    "status": "Error",
                }
            else:
                summary[parser_name]["status"] = "Error"

    return summary


def find_output_dir(client_name):
    """Find the output directory from the parser output."""
    # Build the expected output directory path
    output_dir = os.path.join("data", "clients", client_name, "output")

    # Check if it exists, if not try a different path
    if not os.path.exists(output_dir):
        # Try alternate locations
        alt_output_dir = os.path.join(
            "dataextractai", "data", "clients", client_name, "output"
        )
        if os.path.exists(alt_output_dir):
            output_dir = alt_output_dir
        else:
            print(
                f"Warning: Could not find output directory at {output_dir} or {alt_output_dir}"
            )
            return None

    return output_dir


def create_symlink(client_name):
    """Create a symlink to the client data."""
    # Create the symlink path
    symlink_path = os.path.join("dataextractai", "data", "clients", client_name)

    # Check if the symlink already exists
    if os.path.exists(symlink_path):
        # If it's a symlink, remove it
        if os.path.islink(symlink_path):
            os.unlink(symlink_path)
        # If it's a directory, skip
        else:
            return

    # Create the target directory if it doesn't exist
    target_dir = os.path.join("dataextractai", "data", "clients")
    os.makedirs(target_dir, exist_ok=True)

    # Create the symlink
    source_path = os.path.join("data", "clients", client_name)
    os.symlink(os.path.abspath(source_path), symlink_path)

    click.echo(f"Created symlink to client data at: {symlink_path}")


def print_parser_summary(output_dir):
    """Print a summary of the parser results."""
    if not output_dir or not os.path.exists(output_dir):
        print("No output directory found. Check for errors in the parser execution.")
        return

    # Get the list of created files
    output_files = [f for f in os.listdir(output_dir) if f.endswith((".csv", ".xlsx"))]

    if output_files:
        print(f"\nProcessing complete! Results saved to: {output_dir}")
        print("Parser ran successfully!")
        print(
            f"Output files created: {len(output_files)//2}"
        )  # Divide by 2 since we have CSV and XLSX

        # Group files by parser
        parsers = {}
        for file in sorted(output_files):
            parser_name = file.replace("_output.csv", "").replace("_output.xlsx", "")
            if parser_name not in parsers:
                parsers[parser_name] = []
            parsers[parser_name].append(file)

        # Print parser summary
        print("\nParser execution summary:")
        for parser, files in parsers.items():
            csv_file = next((f for f in files if f.endswith(".csv")), None)
            if csv_file:
                # Try to read the CSV to count transactions
                try:
                    import pandas as pd

                    df = pd.read_csv(os.path.join(output_dir, csv_file))
                    transaction_count = len(df)
                    print(
                        f"  • {parser}: Successfully processed - {transaction_count} transactions"
                    )
                except Exception as e:
                    print(
                        f"  • {parser}: CSV file created but could not count transactions: {e}"
                    )
            else:
                print(f"  • {parser}: No CSV output found")
    else:
        print("No output files were created. Check for errors in the parser output.")


if __name__ == "__main__":
    client_name = "test_client"

    if len(sys.argv) > 1:
        # Use the provided client name
        client_name = sys.argv[1]

    click.echo(f"Setting up test client: {client_name}")
    setup_test_client(client_name)

    click.echo("\nRunning parser test:")
    run_parser_test(client_name)
