"""Interactive menu system for the PDF extractor."""

import questionary
import click
import os
import json
from typing import Optional
from .parsers.run_parsers import run_all_parsers
from .utils.transaction_normalizer import TransactionNormalizer
from .agents.client_profile_manager import ClientProfileManager
from .agents.transaction_classifier import TransactionClassifier
from .utils.config import get_client_config
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get model configurations from environment
OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18")
OPENAI_MODEL_PRECISE = os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31")


def get_client_list():
    """Get list of available clients."""
    client_dir = os.path.join("data", "clients")
    if not os.path.exists(client_dir):
        return []
    return [
        d for d in os.listdir(client_dir) if os.path.isdir(os.path.join(client_dir, d))
    ]


def list_clients():
    """Display all available clients."""
    clients = get_client_list()
    if not clients:
        click.echo("No clients found.")
        return

    click.echo("\nAvailable Clients:")
    for client in clients:
        click.echo(f"- {client}")
    click.echo()


def start_menu():
    """Start the interactive menu system."""
    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                "List Clients",
                "Create/Update Business Profile",
                "Run Parsers",
                "Normalize Transactions",
                "Classify Transactions",
                "Process All (Parse, Normalize, Classify)",
                "Exit",
            ],
        ).ask()

        if action == "Exit":
            break

        elif action == "List Clients":
            list_clients()
            continue

        # Get client selection
        clients = get_client_list()
        if not clients:
            click.echo("No clients found. Please create a client first.")
            continue

        client_name = questionary.select("Select a client:", choices=clients).ask()

        if action == "Create/Update Business Profile":
            try:
                # Try to load existing profile
                profile_manager = ClientProfileManager(client_name)
                existing_profile = profile_manager._load_profile()

                # Use existing values as defaults
                default_business_type = (
                    existing_profile.get("business_type", "")
                    if existing_profile
                    else ""
                )
                default_description = (
                    existing_profile.get("business_description", "")
                    if existing_profile
                    else ""
                )
                default_categories = (
                    ",".join(existing_profile.get("custom_categories", []))
                    if existing_profile
                    else ""
                )

                # Get updated values, using defaults
                business_type = questionary.text(
                    "Enter business type (e.g., 'Restaurant', 'Consulting'):",
                    default=default_business_type,
                ).ask()

                business_description = questionary.text(
                    "Enter detailed business description:", default=default_description
                ).ask()

                custom_categories = questionary.text(
                    "Enter custom expense categories (comma-separated):",
                    default=default_categories,
                ).ask()

                # Update profile with new values
                profile = profile_manager.create_or_update_profile(
                    business_type=business_type,
                    business_description=business_description,
                    custom_categories=(
                        custom_categories.split(",") if custom_categories else None
                    ),
                )
                click.echo(f"Profile created/updated:\n{json.dumps(profile, indent=2)}")
            except Exception as e:
                click.echo(f"Error: {e}")

        elif action == "Run Parsers":
            try:
                config = get_client_config(client_name)
                run_all_parsers(client_name, config)
                click.echo(f"Successfully ran parsers for client: {client_name}")
            except Exception as e:
                click.echo(f"Error: {e}")

        elif action == "Normalize Transactions":
            try:
                normalizer = TransactionNormalizer(client_name)
                transactions_df = normalizer.normalize_transactions()
                if not transactions_df.empty:
                    click.echo(
                        f"Successfully normalized transactions for client: {client_name}"
                    )
                else:
                    click.echo(
                        f"No transactions found to normalize for client: {client_name}"
                    )
            except Exception as e:
                click.echo(f"Error: {e}")

        elif action == "Classify Transactions":
            try:
                # First normalize transactions
                normalizer = TransactionNormalizer(client_name)
                transactions_df = normalizer.normalize_transactions()

                if transactions_df.empty:
                    click.echo(
                        f"No transactions found to classify for client: {client_name}"
                    )
                    continue

                # Then classify transactions
                classifier = TransactionClassifier(client_name)
                classified_df = classifier.classify_transactions(transactions_df)

                if not classified_df.empty:
                    click.echo(
                        f"Successfully classified transactions for client: {client_name}"
                    )
                else:
                    click.echo(
                        f"No transactions were classified for client: {client_name}"
                    )
            except Exception as e:
                click.echo(f"Error: {e}")

        elif action == "Process All (Parse, Normalize, Classify)":
            try:
                # Run parsers
                config = get_client_config(client_name)
                run_all_parsers(client_name, config)
                click.echo(f"Successfully ran parsers for client: {client_name}")

                # Normalize transactions
                normalizer = TransactionNormalizer(client_name)
                transactions_df = normalizer.normalize_transactions()
                if not transactions_df.empty:
                    click.echo(
                        f"Successfully normalized transactions for client: {client_name}"
                    )
                else:
                    click.echo(
                        f"No transactions found to normalize for client: {client_name}"
                    )

                # Classify transactions
                classifier = TransactionClassifier(client_name)
                classified_df = classifier.classify_transactions(transactions_df)
                if not classified_df.empty:
                    click.echo(
                        f"Successfully classified transactions for client: {client_name}"
                    )
                else:
                    click.echo(
                        f"No transactions were classified for client: {client_name}"
                    )
            except Exception as e:
                click.echo(f"Error: {e}")
