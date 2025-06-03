"""Command-line interface for the PDF extractor."""

import click
import os
import logging
from typing import Optional
from .parsers.run_parsers import run_parsers
from .utils.transaction_normalizer import TransactionNormalizer
from .agents.client_profile_manager import ClientProfileManager
from .agents.transaction_classifier import TransactionClassifier
import json
from datetime import datetime
from .utils.config import get_client_config, get_current_paths
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@click.group()
def cli():
    """PDF extractor CLI."""
    pass


@cli.command()
@click.argument("client_name")
@click.option("--input-dir", "-i", help="Input directory for PDF files")
@click.option("--output-dir", "-o", help="Output directory for processed files")
def parse(
    client_name: str, input_dir: Optional[str] = None, output_dir: Optional[str] = None
):
    """Run parsers on PDF files."""
    try:
        # Get client configuration
        config = get_client_config(client_name)

        # Override paths if provided
        if input_dir:
            config["input_dir"] = input_dir
        if output_dir:
            config["output_dir"] = output_dir

        # Get current paths
        paths = get_current_paths(config)

        # Run parsers
        run_parsers(client_name, config)
        logger.info(f"Successfully processed PDF files for {client_name}")

    except Exception as e:
        logger.error(f"Error processing PDF files: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
@click.option("--input-dir", "-i", help="Input directory for CSV files")
@click.option("--output-dir", "-o", help="Output directory for normalized files")
def normalize(
    client_name: str, input_dir: Optional[str] = None, output_dir: Optional[str] = None
):
    """Normalize and consolidate transaction data."""
    try:
        # Get client configuration
        config = get_client_config(client_name)

        # Override paths if provided
        if input_dir:
            config["input_dir"] = input_dir
        if output_dir:
            config["output_dir"] = output_dir

        # Get current paths
        paths = get_current_paths(config)

        # Initialize normalizer
        normalizer = TransactionNormalizer(client_name)

        # Normalize transactions
        transactions_df = normalizer.normalize_transactions(paths["output_paths"])

        # Save normalized transactions
        output_file = os.path.join(paths["output_paths"]["consolidated_core"]["csv"])
        transactions_df.to_csv(output_file, index=False)
        logger.info(f"Successfully normalized transactions for {client_name}")

    except Exception as e:
        logger.error(f"Error normalizing transactions: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
@click.option("--input-file", "-i", help="Input CSV file for classification")
@click.option("--output-file", "-o", help="Output CSV file for classified transactions")
def classify(
    client_name: str,
    input_file: Optional[str] = None,
    output_file: Optional[str] = None,
):
    """Classify transactions using AI."""
    try:
        # Get client configuration
        config = get_client_config(client_name)
        paths = get_current_paths(config)

        # Use provided input file or default
        if not input_file:
            input_file = paths["output_paths"]["consolidated_core"]["csv"]

        # Use provided output file or default
        if not output_file:
            output_file = paths["output_paths"]["consolidated_updated"]["csv"]

        # Initialize classifier
        classifier = TransactionClassifier(client_name)

        # Read transactions
        transactions_df = pd.read_csv(input_file)

        # Classify transactions
        classified_df = classifier.classify_transactions(transactions_df)

        # Save classified transactions
        classified_df.to_csv(output_file, index=False)
        logger.info(f"Successfully classified transactions for {client_name}")

    except Exception as e:
        logger.error(f"Error classifying transactions: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
@click.option("--input-file", "-i", help="Input CSV file for review")
@click.option("--output-file", "-o", help="Output CSV file for reviewed transactions")
def review(
    client_name: str,
    input_file: Optional[str] = None,
    output_file: Optional[str] = None,
):
    """Review and approve classified transactions."""
    try:
        # Get client configuration
        config = get_client_config(client_name)
        paths = get_current_paths(config)

        # Use provided input file or default
        if not input_file:
            input_file = paths["output_paths"]["consolidated_updated"]["csv"]

        # Use provided output file or default
        if not output_file:
            output_file = paths["output_paths"]["consolidated_batched"]["csv"]

        # Read transactions
        transactions_df = pd.read_csv(input_file)

        # TODO: Implement review workflow
        # This will be implemented in a future update
        logger.info("Review workflow not yet implemented")

        # For now, just copy the file
        transactions_df.to_csv(output_file, index=False)
        logger.info(f"Successfully copied transactions for review for {client_name}")

    except Exception as e:
        logger.error(f"Error reviewing transactions: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
@click.option("--input-file", "-i", help="Input CSV file for upload")
@click.option("--sheet-name", "-s", help="Google Sheet name")
def upload(
    client_name: str, input_file: Optional[str] = None, sheet_name: Optional[str] = None
):
    """Upload classified transactions to Google Sheets."""
    try:
        # Get client configuration
        config = get_client_config(client_name)
        paths = get_current_paths(config)

        # Use provided input file or default
        if not input_file:
            input_file = paths["output_paths"]["consolidated_batched"]["csv"]

        # Use provided sheet name or default
        if not sheet_name:
            sheet_name = (
                f"{client_name}_Transactions_{datetime.now().strftime('%Y%m%d')}"
            )

        # TODO: Implement Google Sheets upload
        # This will be implemented in a future update
        logger.info("Google Sheets upload not yet implemented")

    except Exception as e:
        logger.error(f"Error uploading to Google Sheets: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
@click.option("--input-dir", "-i", help="Input directory for PDF files")
@click.option("--output-dir", "-o", help="Output directory for processed files")
def process_all(
    client_name: str, input_dir: Optional[str] = None, output_dir: Optional[str] = None
):
    """Run all processing steps in sequence."""
    try:
        # Run each step
        parse(client_name, input_dir, output_dir)
        normalize(client_name, input_dir, output_dir)
        classify(client_name)
        review(client_name)
        upload(client_name)

        logger.info(f"Successfully completed all processing steps for {client_name}")

    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
        raise click.Abort()


if __name__ == "__main__":
    cli()
