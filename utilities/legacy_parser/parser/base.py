import os
import time
import glob
from pathlib import Path
import click
import pandas as pd
from rich.progress import Progress
import sys
import shutil


def check_for_pdf_files(client_name: str) -> bool:
    """Check if the client has any PDF files to process.

    Args:
        client_name: Name of the client

    Returns:
        bool: True if client has PDF files, False otherwise
    """
    client_dir = os.path.join("data", "clients", client_name)
    input_dir = os.path.join(client_dir, "input")

    # Check if client directory exists
    if not os.path.exists(client_dir):
        click.echo(f"Client directory not found: {client_dir}")
        return False

    # Check if input directory exists
    if not os.path.exists(input_dir):
        click.echo(f"Input directory not found: {input_dir}")
        return False

    # Define parser directories
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
        "firstrepublic_bank",
    ]

    # Check each parser directory for PDF files
    pdf_files_count = 0
    directories_with_files = []

    for parser in parser_dirs:
        parser_input_dir = os.path.join(input_dir, parser)

        # Skip if directory doesn't exist
        if not os.path.exists(parser_input_dir):
            continue

        # Check if any PDF files exist using glob (more reliable)
        pdf_files = glob.glob(os.path.join(parser_input_dir, "*.pdf"))
        if pdf_files:
            pdf_files_count += len(pdf_files)
            directories_with_files.append(parser)

    if pdf_files_count > 0:
        # Log where the files were found
        click.echo(f"\nFound {pdf_files_count} PDF files in the following directories:")
        for parser in directories_with_files:
            dir_path = os.path.join(input_dir, parser)
            found_files = glob.glob(os.path.join(dir_path, "*.pdf"))
            click.echo(f"  - {parser}: {len(found_files)} files")

        return True

    return False


def run_parser(client_name: str) -> bool:
    """Run parsers for the specified client by directly calling the run_all_parsers function.

    Args:
        client_name: Name of the client

    Returns:
        bool: True if parsing was successful, False otherwise
    """
    # Define paths
    client_dir = os.path.join("data", "clients", client_name)

    # Check if client directory exists
    if not os.path.exists(client_dir):
        click.echo(f"Error: Client directory not found: {client_dir}")
        return False

    # Display header
    click.echo("\nRunning parsers for PDFs in client directory...")

    # The simplest and most reliable approach is to use a subprocess to run the parsers
    try:
        # Import the function directly - much more reliable than dynamic loading
        from dataextractai.parsers.run_parsers import run_all_parsers
        from dataextractai.utils.config import get_client_config

        # Ensure the data structure in dataextractai matches what our app expects
        dataextractai_data_dir = os.path.join("dataextractai", "data")
        dataextractai_client_dir = os.path.join(
            dataextractai_data_dir, "clients", client_name
        )

        # Create parent directories if needed
        os.makedirs(os.path.dirname(dataextractai_client_dir), exist_ok=True)

        # Create symlink or copy to dataextractai expected location
        try:
            # Remove existing symlink/directory if it exists
            if os.path.lexists(dataextractai_client_dir):
                if os.path.islink(dataextractai_client_dir):
                    os.remove(dataextractai_client_dir)
                else:
                    shutil.rmtree(dataextractai_client_dir)

            # Create symlink (Unix) or copy directory (Windows)
            if sys.platform == "win32":
                # On Windows, copy the directory
                shutil.copytree(client_dir, dataextractai_client_dir)
                click.echo(f"Copied client data to: {dataextractai_client_dir}")
            else:
                # On Unix-like systems, create a symlink
                abs_client_dir = os.path.abspath(client_dir)
                os.symlink(
                    abs_client_dir, dataextractai_client_dir, target_is_directory=True
                )
                click.echo(
                    f"Created symlink to client data at: {dataextractai_client_dir}"
                )
        except Exception as e:
            click.echo(f"Warning: Error preparing client data directory: {str(e)}")
            # Continue anyway, as we'll modify the config paths

        # Get client config
        config = get_client_config(client_name)
        if not config:
            click.echo(
                f"Error: Could not load configuration for client '{client_name}'"
            )
            return False

        # Ensure client_name is in the config
        config["client_name"] = client_name

        # Override data directory paths to match our app's structure
        config["data_dir"] = "data/clients"
        config["input_dir"] = "data/clients"
        config["output_dir"] = "data/clients"
        config["batch_output_dir"] = "data/clients"

        # Ensure all required directories exist
        input_dir = os.path.join(client_dir, "input")
        output_dir = os.path.join(client_dir, "output")

        # Create the directories if they don't exist
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # Create parser directories if they don't exist
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
            "firstrepublic_bank",
        ]

        for parser in parser_dirs:
            parser_dir = os.path.join(input_dir, parser)
            if not os.path.exists(parser_dir):
                os.makedirs(parser_dir, exist_ok=True)
                click.echo(f"Created missing parser directory: {parser_dir}")

        # Run the parsers
        click.echo(f"Starting PDF processing for client: {client_name}")
        click.echo("This may take a while depending on the number and size of PDFs...")

        # Debug: list all PDF files we can find
        found_pdfs = []
        for parser in parser_dirs:
            parser_dir = os.path.join(input_dir, parser)
            pdf_files = glob.glob(os.path.join(parser_dir, "*.pdf"))
            if pdf_files:
                found_pdfs.extend(pdf_files)
                click.echo(f"Found {len(pdf_files)} PDF files in {parser_dir}")

        if not found_pdfs:
            click.echo("Warning: No PDF files found in any parser directory!")
            return False

        # Patch the SOURCE_DIR in each parser module before running
        # This is critical to make the parsers use the client-specific directories
        try:
            # Amazon parser
            import dataextractai.parsers.amazon_parser as amazon_parser

            amazon_parser.SOURCE_DIR = os.path.join(input_dir, "amazon")
            amazon_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "amazon_output.csv"
            )
            amazon_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "amazon_output.xlsx"
            )

            # Bank of America bank parser
            import dataextractai.parsers.bofa_bank_parser as bofa_bank_parser

            bofa_bank_parser.SOURCE_DIR = os.path.join(input_dir, "bofa_bank")
            bofa_bank_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "bofa_bank_output.csv"
            )
            bofa_bank_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "bofa_bank_output.xlsx"
            )

            # Bank of America Visa parser
            import dataextractai.parsers.bofa_visa_parser as bofa_visa_parser

            bofa_visa_parser.SOURCE_DIR = os.path.join(input_dir, "bofa_visa")
            bofa_visa_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "bofa_visa_output.csv"
            )
            bofa_visa_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "bofa_visa_output.xlsx"
            )

            # Chase Visa parser
            import dataextractai.parsers.chase_visa_parser as chase_visa_parser

            chase_visa_parser.SOURCE_DIR = os.path.join(input_dir, "chase_visa")
            chase_visa_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "chase_visa_output.csv"
            )
            chase_visa_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "chase_visa_output.xlsx"
            )

            # Wells Fargo Bank parser
            import dataextractai.parsers.wellsfargo_bank_parser as wellsfargo_bank_parser

            wellsfargo_bank_parser.SOURCE_DIR = os.path.join(
                input_dir, "wellsfargo_bank"
            )
            wellsfargo_bank_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "wellsfargo_bank_output.csv"
            )
            wellsfargo_bank_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "wellsfargo_bank_output.xlsx"
            )

            # Wells Fargo Mastercard parser
            import dataextractai.parsers.wellsfargo_mastercard_parser as wellsfargo_mastercard_parser

            wellsfargo_mastercard_parser.SOURCE_DIR = os.path.join(
                input_dir, "wellsfargo_mastercard"
            )
            wellsfargo_mastercard_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "wellsfargo_mastercard_output.csv"
            )
            wellsfargo_mastercard_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "wellsfargo_mastercard_output.xlsx"
            )

            # Wells Fargo Bank CSV parser
            import dataextractai.parsers.wellsfargo_bank_csv_parser as wellsfargo_bank_csv_parser

            wellsfargo_bank_csv_parser.SOURCE_DIR = os.path.join(
                input_dir, "wellsfargo_bank_csv"
            )
            wellsfargo_bank_csv_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "wellsfargo_bank_csv_output.csv"
            )
            wellsfargo_bank_csv_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "wellsfargo_bank_csv_output.xlsx"
            )

            # Wells Fargo Visa parser
            import dataextractai.parsers.wellsfargo_visa_parser as wellsfargo_visa_parser

            wellsfargo_visa_parser.SOURCE_DIR = os.path.join(
                input_dir, "wellsfargo_visa"
            )
            wellsfargo_visa_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "wellsfargo_visa_output.csv"
            )
            wellsfargo_visa_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "wellsfargo_visa_output.xlsx"
            )

            # First Republic Bank parser
            import dataextractai.parsers.first_republic_bank_parser as first_republic_bank_parser

            first_republic_bank_parser.SOURCE_DIR = os.path.join(
                input_dir, "first_republic_bank"
            )
            # Check if the alternate directory exists and use it if so
            if os.path.exists(os.path.join(input_dir, "firstrepublic_bank")):
                first_republic_bank_parser.SOURCE_DIR = os.path.join(
                    input_dir, "firstrepublic_bank"
                )
            first_republic_bank_parser.OUTPUT_PATH_CSV = os.path.join(
                output_dir, "first_republic_bank_output.csv"
            )
            first_republic_bank_parser.OUTPUT_PATH_XLSX = os.path.join(
                output_dir, "first_republic_bank_output.xlsx"
            )

            click.echo(
                "Successfully patched parser paths to use client-specific directories"
            )
        except Exception as e:
            click.echo(f"Warning: Error patching parser paths: {str(e)}")
            click.echo("Some parsers may not work correctly")

        # Run the actual parsers
        num_processed = run_all_parsers(client_name, config)

        if num_processed > 0:
            click.echo(
                f"\nProcessing complete! Processed {num_processed} transactions."
            )
            click.echo(f"Results saved to: {os.path.join(client_dir, 'output')}")
            return True
        else:
            click.echo(
                "\nNo transactions were processed. Please check your PDF files and try again."
            )
            click.echo(
                "PDF files should be placed in the appropriate input directory for each parser type:"
            )
            for parser in parser_dirs:
                click.echo(f"  - {os.path.join(client_dir, 'input', parser)}")
            return False

    except ImportError as e:
        click.echo(f"Error: Could not import parser modules: {str(e)}")
        click.echo("Make sure dataextractai package is properly installed.")
        return False
    except Exception as e:
        click.echo(f"Error running parsers: {str(e)}")
        return False


def create_test_pdf(client_name: str, parser_type: str = "amazon") -> bool:
    """Create a test PDF file for demonstration purposes.

    Args:
        client_name: Name of the client
        parser_type: Type of parser to create a test file for

    Returns:
        bool: True if created successfully, False otherwise
    """
    try:
        # Define paths
        client_dir = os.path.join("data", "clients", client_name)
        input_dir = os.path.join(client_dir, "input", parser_type)

        # Ensure directory exists
        os.makedirs(input_dir, exist_ok=True)

        # Create a simple test PDF file
        import io
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter

        # Create a buffer and PDF document
        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)

        # Add some content
        pdf.setFont("Helvetica", 12)
        pdf.drawString(100, 750, f"Test PDF for {parser_type} parser")
        pdf.drawString(100, 730, f"Client: {client_name}")
        pdf.drawString(100, 710, f"Date: {time.strftime('%Y-%m-%d')}")
        pdf.drawString(100, 690, "This is a test file for demonstration purposes only.")
        pdf.drawString(
            100, 670, "In a real application, you would place actual bank statements or"
        )
        pdf.drawString(
            100, 650, "other financial documents in these input directories."
        )

        # Save the PDF
        pdf.save()

        # Write the buffer content to a file
        with open(os.path.join(input_dir, "test_file.pdf"), "wb") as f:
            f.write(buffer.getvalue())

        return True
    except Exception as e:
        click.echo(f"Error creating test PDF: {str(e)}")
        return False
