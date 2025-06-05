"""Command-line interface for the PDF extractor."""

import logging
import click
import os
import glob
import pandas as pd
from io import StringIO
from typing import Optional
from .parsers.run_parsers import run_parsers
from .utils.transaction_normalizer import TransactionNormalizer
from .agents.client_profile_manager import ClientProfileManager
from .agents.transaction_classifier import TransactionClassifier
import json
from datetime import datetime
from .utils.config import get_client_config, get_current_paths

# Configure logging before any other imports
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
@click.option(
    "--per-statement-raw/--no-per-statement-raw",
    default=False,
    help="Dump raw extracted data for each statement file (default: False)",
)
def parse(
    client_name: str,
    input_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    per_statement_raw: bool = False,
):
    """Run parsers on PDF files. Optionally dump per-statement raw extracted data for debugging."""
    try:
        # Get client configuration
        config = get_client_config(client_name)

        # Override paths if provided
        if input_dir:
            config["input_dir"] = input_dir
        if output_dir:
            config["output_dir"] = output_dir
        # Ensure output_dir is always set
        if "output_dir" not in config or not config["output_dir"]:
            config["output_dir"] = "data/clients"

        # Get current paths
        paths = get_current_paths(config)

        # Run parsers
        run_parsers(client_name, config, dump_per_statement_raw=per_statement_raw)
        logger.info(f"Successfully processed PDF files for {client_name}")

    except Exception as e:
        logger.error(f"Error processing PDF files: {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
@click.option("--input-dir", "-i", help="Input directory for CSV files")
@click.option("--output-dir", "-o", help="Output directory for normalized files")
@click.option(
    "--per-statement/--no-per-statement",
    default=True,
    help="Dump individual normalized CSVs for each statement file (default: True)",
)
@click.option(
    "--diagnostics/--no-diagnostics",
    default=False,
    help="Print diagnostics after normalization: row counts, sample rows, and warnings if Django is using raw data. Also writes to diagnostics_summary.txt in the output directory.",
)
def normalize(
    client_name: str,
    input_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    per_statement: bool = True,
    diagnostics: bool = False,
):
    """Normalize and consolidate transaction data. Optionally dump per-statement normalized files. Use --diagnostics to print row counts, sample rows, and warnings. Also writes diagnostics to diagnostics_summary.txt."""
    try:
        # Get client configuration
        config = get_client_config(client_name)

        # Override paths if provided
        if input_dir:
            config["input_dir"] = input_dir
        if output_dir:
            config["output_dir"] = output_dir
        if "output_dir" not in config:
            config["output_dir"] = os.path.join(
                "data", "clients", client_name, "output"
            )

        # Normalize transactions
        normalizer = TransactionNormalizer(
            client_name, dump_per_statement=per_statement
        )
        transactions_df = normalizer.normalize_transactions()

        if diagnostics:
            output_dir = config["output_dir"]
            summary = StringIO()

            def _print(*args, **kwargs):
                print(*args, **kwargs)
                print(*args, **kwargs, file=summary)

            _print("\n=== Diagnostics ===")
            # 1. Per-statement raw files
            raw_dir = os.path.join(output_dir, "raw_per_statement")
            raw_files = glob.glob(os.path.join(raw_dir, "*.raw.csv"))
            total_raw_rows = 0
            _print(f"Per-statement raw files in {raw_dir}:")
            for f in raw_files:
                df = pd.read_csv(f)
                _print(f"  {os.path.basename(f)}: {len(df)} rows")
                total_raw_rows += len(df)
                _print(df.head(2).to_string(index=False))
            _print(f"Total rows in all raw_per_statement files: {total_raw_rows}")
            # 2. Aggregate raw output
            agg_raw_path = os.path.join(output_dir, f"{client_name}_output.csv")
            if os.path.exists(agg_raw_path):
                df_agg = pd.read_csv(agg_raw_path)
                _print(f"Aggregate raw output: {agg_raw_path}: {len(df_agg)} rows")
                _print(df_agg.head(2).to_string(index=False))
            else:
                _print(f"Aggregate raw output not found: {agg_raw_path}")
            # 3. Normalized output
            norm_path = os.path.join(
                output_dir, f"{client_name}_normalized_transactions.csv"
            )
            if os.path.exists(norm_path):
                df_norm = pd.read_csv(norm_path)
                _print(f"Normalized output: {norm_path}: {len(df_norm)} rows")
                _print(df_norm.head(2).to_string(index=False))
            else:
                _print(f"Normalized output not found: {norm_path}")
            # 4. Problem rows
            problem_rows = normalizer.get_problem_rows()
            _print(f"Problem rows: {len(problem_rows)}")
            if not problem_rows.empty:
                _print(problem_rows.head(2).to_string(index=False))
            # 5. Warnings
            if not os.path.exists(norm_path) or (
                os.path.exists(agg_raw_path)
                and os.path.getsize(norm_path) < os.path.getsize(agg_raw_path)
            ):
                _print(
                    "[WARNING] Django may be ingesting raw data or missing normalized data!"
                )
            _print("=== End Diagnostics ===\n")

            # Write diagnostics to file
            diag_path = os.path.join(output_dir, "diagnostics_summary.txt")
            with open(diag_path, "w") as f:
                f.write(summary.getvalue())
            print(f"Diagnostics summary written to {diag_path}")

        click.echo("Normalization complete.")
    except Exception as e:
        click.echo(f"Error normalizing transactions: {e}")
        click.echo("Aborted!")


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
