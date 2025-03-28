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
def parse(client_name: str):
    """Run parsers for a specific client."""
    try:
        run_parsers(client_name)
        logger.info(f"Successfully ran parsers for client: {client_name}")
    except Exception as e:
        logger.error(f"Error running parsers: {e}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
def normalize(client_name: str):
    """Normalize transactions for a specific client."""
    try:
        normalizer = TransactionNormalizer(client_name)
        transactions_df = normalizer.normalize_transactions()
        if not transactions_df.empty:
            logger.info(
                f"Successfully normalized transactions for client: {client_name}"
            )
        else:
            logger.warning(
                f"No transactions found to normalize for client: {client_name}"
            )
    except Exception as e:
        logger.error(f"Error normalizing transactions: {e}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
@click.option(
    "--business-type",
    required=True,
    help="Type of business (e.g., 'Restaurant', 'Consulting')",
)
@click.option(
    "--business-description", required=True, help="Detailed description of the business"
)
@click.option(
    "--custom-categories", help="Comma-separated list of custom expense categories"
)
def create_profile(
    client_name: str,
    business_type: str,
    business_description: str,
    custom_categories: Optional[str],
):
    """Create or update a client's business profile."""
    try:
        # Parse custom categories if provided
        categories = custom_categories.split(",") if custom_categories else None

        # Create or update profile
        profile_manager = ClientProfileManager(client_name)
        profile = profile_manager.create_or_update_profile(
            business_type=business_type,
            business_description=business_description,
            custom_categories=categories,
        )

        logger.info(f"Successfully created/updated profile for client: {client_name}")
        click.echo(f"Profile created/updated:\n{json.dumps(profile, indent=2)}")
    except Exception as e:
        logger.error(f"Error creating/updating profile: {e}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
def classify(client_name: str):
    """Classify transactions for a specific client."""
    try:
        # First normalize transactions
        normalizer = TransactionNormalizer(client_name)
        transactions_df = normalizer.normalize_transactions()

        if transactions_df.empty:
            logger.warning(
                f"No transactions found to classify for client: {client_name}"
            )
            return

        # Then classify transactions
        classifier = TransactionClassifier(client_name)
        classified_df = classifier.classify_transactions(transactions_df)

        if not classified_df.empty:
            logger.info(
                f"Successfully classified transactions for client: {client_name}"
            )
        else:
            logger.warning(f"No transactions were classified for client: {client_name}")
    except Exception as e:
        logger.error(f"Error classifying transactions: {e}")
        raise click.Abort()


@cli.command()
@click.argument("client_name")
def process_all(client_name: str):
    """Run all processing steps for a client: parse, normalize, and classify."""
    try:
        # Run parsers
        run_parsers(client_name)
        logger.info(f"Successfully ran parsers for client: {client_name}")

        # Normalize transactions
        normalizer = TransactionNormalizer(client_name)
        transactions_df = normalizer.normalize_transactions()
        if not transactions_df.empty:
            logger.info(
                f"Successfully normalized transactions for client: {client_name}"
            )
        else:
            logger.warning(
                f"No transactions found to normalize for client: {client_name}"
            )

        # Classify transactions
        classifier = TransactionClassifier(client_name)
        classified_df = classifier.classify_transactions(transactions_df)
        if not classified_df.empty:
            logger.info(
                f"Successfully classified transactions for client: {client_name}"
            )
        else:
            logger.warning(f"No transactions were classified for client: {client_name}")

    except Exception as e:
        logger.error(f"Error in processing pipeline: {e}")
        raise click.Abort()


if __name__ == "__main__":
    cli()
