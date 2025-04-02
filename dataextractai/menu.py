"""Interactive menu system for the PDF extractor."""

import questionary
import click
import os
import json
import pandas as pd
from typing import Optional, List
from .parsers.run_parsers import run_all_parsers
from .utils.transaction_normalizer import TransactionNormalizer
from .agents.client_profile_manager import ClientProfileManager
from .agents.transaction_classifier import TransactionClassifier
from .utils.config import get_client_config, get_current_paths
from .sheets.sheet_manager import GoogleSheetManager
from .sheets.config import get_sheets_config, save_sheets_config
from .db.client_db import ClientDB
from dotenv import load_dotenv
import sqlite3

# Load environment variables
load_dotenv()

# Get model configurations from environment
OPENAI_MODEL_FAST = os.getenv("OPENAI_MODEL_FAST", "gpt-4o-mini-2024-07-18")
OPENAI_MODEL_PRECISE = os.getenv("OPENAI_MODEL_PRECISE", "o3-mini-2025-01-31")


def get_client_list():
    """Get list of available clients."""
    # First check database
    db = ClientDB()
    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.execute("SELECT name FROM clients ORDER BY name")
        clients = [row[0] for row in cursor.fetchall()]

    # Then check filesystem for backward compatibility
    client_dir = os.path.join("data", "clients")
    if os.path.exists(client_dir):
        fs_clients = [
            d
            for d in os.listdir(client_dir)
            if os.path.isdir(os.path.join(client_dir, d))
        ]
        # Add any clients from filesystem not in database
        for client in fs_clients:
            if client not in clients:
                clients.append(client)

    return sorted(clients)


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


def handle_sheets_menu(client_name: str):
    """Handle Google Sheets operations."""
    try:
        # Get credentials path from environment
        credentials_path = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
        if not credentials_path:
            click.echo(
                "Error: GOOGLE_SHEETS_CREDENTIALS_PATH environment variable not set."
            )
            return

        sheet_manager = GoogleSheetManager(credentials_path)

        # Get client's sheet configuration
        config = get_sheets_config(client_name)

        # Get transactions from database
        db = ClientDB()
        transactions_df = db.load_normalized_transactions(client_name)

        if transactions_df.empty:
            click.echo("No transactions found for client")
            return

        # Upload to sheets
        sheet_id = sheet_manager.update_client_sheet(
            client_name=client_name,
            data=transactions_df,
            sheet_id=config.get("sheet_id"),
        )

        # Update configuration with new sheet ID
        config["sheet_id"] = sheet_id
        save_sheets_config(client_name, config)

        click.echo(f"Successfully uploaded transactions to Google Sheets")

    except Exception as e:
        click.echo(f"Error with Google Sheets operation: {e}")


def handle_excel_export(client_name: str):
    """Handle Excel report generation."""
    try:
        # Get transactions from database
        db = ClientDB()
        transactions_df = db.load_normalized_transactions(client_name)

        if transactions_df.empty:
            click.echo("No transactions found for client")
            return

        # Create Excel report
        output_dir = os.path.join("data", "clients", client_name, "output")
        os.makedirs(output_dir, exist_ok=True)
        excel_output = os.path.join(output_dir, f"{client_name}_report.xlsx")

        # Create Excel report
        from .sheets.excel_formatter import ExcelReportFormatter

        formatter = ExcelReportFormatter()
        formatter.create_report(
            data=transactions_df, output_path=excel_output, client_name=client_name
        )

        click.echo(f"Successfully created Excel report at: {excel_output}")

    except Exception as e:
        click.echo(f"Error creating Excel report: {e}")


def sync_transactions_to_db(client_name: str):
    """Sync normalized transactions from CSV to SQLite database."""
    try:
        # Get paths
        config = get_client_config(client_name)
        paths = get_current_paths(config)
        csv_path = os.path.join(
            "data",
            "clients",
            client_name,
            "output",
            f"{client_name}_normalized_transactions.csv",
        )

        if not os.path.exists(csv_path):
            click.echo(f"No normalized transactions file found at: {csv_path}")
            return

        # Read CSV file
        df = pd.read_csv(csv_path)
        if df.empty:
            click.echo("No transactions found in CSV file")
            return

        # Initialize database
        db = ClientDB()

        # Confirm with user
        click.echo(f"\nFound {len(df)} transactions in CSV file.")
        if questionary.confirm(
            "This will replace all existing transactions in the database. Continue?"
        ).ask():
            # Save to database
            db.save_normalized_transactions(client_name, df)
            click.echo(f"Successfully synced {len(df)} transactions to database")
        else:
            click.echo("Operation cancelled")

    except Exception as e:
        click.echo(f"Error syncing transactions to database: {e}")


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
                "\nTransaction Classification (Three-Pass Process):",
                "Pass 1: Identify Payees (Fast Mode)",
                "Pass 1: Identify Payees (Precise Mode)",
                "Pass 2: Assign Categories (Fast Mode)",
                "Pass 2: Assign Categories (Precise Mode)",
                "Pass 3: Classify Transactions (Fast Mode)",
                "Pass 3: Classify Transactions (Precise Mode)",
                "\nBatch Processing Options:",
                "Process All Passes (Fast Mode)",
                "Process All Passes (Precise Mode)",
                "Process Row Range (Fast Mode)",
                "Process Row Range (Precise Mode)",
                "Resume Processing from Pass",
                "\nData Management:",
                "Sync Transactions to Database",
                "Export to Excel Report",
                "Upload to Google Sheets",
                "Exit",
            ],
        ).ask()

        if action == "Exit":
            break

        elif action == "List Clients":
            list_clients()
            continue

        # Get client selection for other actions
        clients = get_client_list()
        if not clients:
            click.echo("No clients found. Please create a client first.")
            continue

        client_name = questionary.select("Select a client:", choices=clients).ask()

        if action == "Create/Update Business Profile":
            try:
                # Try to load existing profile from database
                db = ClientDB()
                existing_profile = db.load_profile(client_name)

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
                    existing_profile.get("custom_categories", [])
                    if existing_profile
                    else []
                )

                # Get new values
                business_type = questionary.text(
                    "Business Type:", default=default_business_type
                ).ask()
                business_description = questionary.text(
                    "Business Description:", default=default_description
                ).ask()

                # Handle categories
                categories = []
                if default_categories:
                    click.echo("\nExisting Categories:")
                    for cat in default_categories:
                        click.echo(f"- {cat}")
                    keep_categories = questionary.confirm(
                        "Keep existing categories?"
                    ).ask()
                    if keep_categories:
                        categories = default_categories

                while questionary.confirm("Add a category?").ask():
                    category = questionary.text("Enter category:").ask()
                    if category:
                        categories.append(category)

                # Create profile
                profile = {
                    "business_type": business_type,
                    "business_description": business_description,
                    "custom_categories": categories,
                }

                # Save to database
                db.save_profile(client_name, profile)
                click.echo("Business profile saved successfully.")

            except Exception as e:
                click.echo(f"Error updating business profile: {e}")

        elif action == "Run Parsers":
            try:
                # Get client configuration
                config = get_client_config(client_name)
                run_all_parsers(client_name, config)
            except Exception as e:
                click.echo(f"Error running parsers: {e}")

        elif action == "Normalize Transactions":
            try:
                normalizer = TransactionNormalizer(client_name)
                transactions_df = normalizer.normalize_transactions()
                if not transactions_df.empty:
                    click.echo(
                        f"Successfully normalized {len(transactions_df)} transactions"
                    )
            except Exception as e:
                click.echo(f"Error normalizing transactions: {e}")

        elif action.startswith("Pass ") or action.startswith("Process "):
            try:
                # Get transactions from database
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)

                if transactions_df.empty:
                    click.echo(
                        "No transactions found. Please normalize transactions first."
                    )
                    continue

                # Get business profile
                profile = db.load_profile(client_name)
                if not profile:
                    click.echo("No business profile found. Please create one first.")
                    continue

                # Initialize classifier
                classifier = TransactionClassifier(
                    client_name=client_name,
                    model_type=(
                        OPENAI_MODEL_PRECISE
                        if "Precise" in action
                        else OPENAI_MODEL_FAST
                    ),
                )

                # Process transactions
                if "Row Range" in action:
                    start_row = questionary.text(
                        "Start row (1-based):", default="1"
                    ).ask()
                    end_row = questionary.text(
                        f"End row (1-{len(transactions_df)}):",
                        default=str(len(transactions_df)),
                    ).ask()
                    try:
                        start_row = max(1, int(start_row))
                        end_row = min(len(transactions_df), int(end_row))
                        transactions_df = transactions_df.iloc[
                            start_row - 1 : end_row
                        ].copy()
                    except ValueError:
                        click.echo("Invalid row numbers")
                        continue

                if "Pass 1" in action or "Process All" in action:
                    transactions_df = classifier.identify_payees(transactions_df)
                if "Pass 2" in action or "Process All" in action:
                    transactions_df = classifier.assign_categories(transactions_df)
                if "Pass 3" in action or "Process All" in action:
                    transactions_df = classifier.classify_transactions(transactions_df)

                # Save results back to database
                db.save_normalized_transactions(client_name, transactions_df)
                click.echo("Successfully processed transactions")

            except Exception as e:
                click.echo(f"Error processing transactions: {e}")

        elif action == "Sync Transactions to Database":
            try:
                sync_transactions_to_db(client_name)
            except Exception as e:
                click.echo(f"Error syncing transactions: {e}")

        elif action == "Export to Excel Report":
            handle_excel_export(client_name)

        elif action == "Upload to Google Sheets":
            handle_sheets_menu(client_name)


if __name__ == "__main__":
    start_menu()
