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

        # Find final files in client's output directory
        output_dir = os.path.join("data", "clients", client_name, "output")
        if not os.path.exists(output_dir):
            click.echo(f"No output directory found for client: {client_name}")
            return

        final_files = [f for f in os.listdir(output_dir) if "final" in f.lower()]
        if not final_files:
            click.echo("No final files found in output directory")
            return

        # Select file to upload
        file_choice = questionary.select(
            "Select file to upload:", choices=final_files + ["Cancel"]
        ).ask()

        if file_choice == "Cancel":
            return

        # Upload file
        file_path = os.path.join(output_dir, file_choice)
        sheet_id = sheet_manager.update_client_sheet(
            client_name=client_name,
            data_file=file_path,
            sheet_id=config.get("sheet_id"),
        )

        # Update configuration with new sheet ID
        config["sheet_id"] = sheet_id
        save_sheets_config(client_name, config)

        click.echo(f"Successfully uploaded {file_choice} to Google Sheets")

    except Exception as e:
        click.echo(f"Error with Google Sheets operation: {e}")


def handle_excel_export(client_name: str):
    """Handle Excel report generation."""
    try:
        # Find final files in client's output directory
        output_dir = os.path.join("data", "clients", client_name, "output")
        if not os.path.exists(output_dir):
            click.echo(f"No output directory found for client: {client_name}")
            return

        final_files = [f for f in os.listdir(output_dir) if "final" in f.lower()]
        if not final_files:
            click.echo("No final files found in output directory")
            return

        # Select file to process
        file_choice = questionary.select(
            "Select file to create Excel report from:", choices=final_files + ["Cancel"]
        ).ask()

        if file_choice == "Cancel":
            return

        # Create Excel report
        file_path = os.path.join(output_dir, file_choice)
        excel_output = os.path.join(output_dir, f"{client_name}_report.xlsx")

        # Read the CSV data
        df = pd.read_csv(file_path)

        # Create Excel report
        from .sheets.excel_formatter import ExcelReportFormatter

        formatter = ExcelReportFormatter()
        formatter.create_report(
            data=df, output_path=excel_output, client_name=client_name
        )

        click.echo(f"Successfully created Excel report at: {excel_output}")

    except Exception as e:
        click.echo(f"Error creating Excel report: {e}")


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
                "\nData Export:",
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
                    ", ".join(existing_profile.get("custom_categories", []))
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

                # Clean up custom categories
                if custom_categories:
                    # Split by comma, clean each category, and filter out empty strings
                    cleaned_categories = [
                        cat.strip().title()  # Clean up formatting
                        for cat in custom_categories.split(",")
                        if cat.strip()  # Remove empty strings
                    ]
                else:
                    cleaned_categories = None

                # Update profile with new values
                profile = profile_manager.create_or_update_profile(
                    business_type=business_type,
                    business_description=business_description,
                    custom_categories=cleaned_categories,
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

        elif action == "Export to Excel Report":
            handle_excel_export(client_name)
        elif action == "Upload to Google Sheets":
            handle_sheets_menu(client_name)

        elif action in [
            "Pass 1: Identify Payees (Fast Mode)",
            "Pass 1: Identify Payees (Precise Mode)",
            "Pass 2: Assign Categories (Fast Mode)",
            "Pass 2: Assign Categories (Precise Mode)",
            "Pass 3: Classify Transactions (Fast Mode)",
            "Pass 3: Classify Transactions (Precise Mode)",
            "Process All Passes (Fast Mode)",
            "Process All Passes (Precise Mode)",
            "Process Row Range (Fast Mode)",
            "Process Row Range (Precise Mode)",
            "Resume Processing from Pass",
        ]:
            try:
                # Set LLM mode
                llm_mode = "fast" if "Fast Mode" in action else "precise"
                os.environ["OPENAI_MODEL_FAST"] = OPENAI_MODEL_FAST
                os.environ["OPENAI_MODEL_PRECISE"] = OPENAI_MODEL_PRECISE

                # Get paths
                config = get_client_config(client_name)
                paths = get_current_paths(config)

                # Read normalized transactions
                normalized_file = os.path.join(
                    paths["output_paths"]["consolidated_core"]["csv"].replace(
                        "consolidated_core_output.csv",
                        f"{client_name.replace(' ', '_')}_normalized_transactions.csv",
                    )
                )

                if not os.path.exists(normalized_file):
                    click.echo(
                        f"No normalized transactions found for client: {client_name}"
                    )
                    continue

                # Read transactions
                transactions_df = pd.read_csv(normalized_file)
                if transactions_df.empty:
                    click.echo(f"No transactions found in {normalized_file}")
                    continue

                # Get row range if needed
                start_row = None
                end_row = None
                if "Row Range" in action:
                    start_row = int(
                        questionary.text("Enter starting row (0-based):").ask()
                    )
                    end_row = int(
                        questionary.text("Enter ending row (exclusive):").ask()
                    )

                # Get resume pass if needed
                resume_from_pass = None
                if action == "Resume Processing from Pass":
                    resume_from_pass = int(
                        questionary.select(
                            "Select pass to resume from:",
                            choices=[
                                "1 - Payee Identification",
                                "2 - Category Assignment",
                                "3 - Classification",
                            ],
                        )
                        .ask()
                        .split(" - ")[0]
                    )
                elif "Pass 1" in action:
                    resume_from_pass = 1
                elif "Pass 2" in action:
                    resume_from_pass = 2
                elif "Pass 3" in action:
                    resume_from_pass = 3

                # Classify transactions
                classifier = TransactionClassifier(
                    client_name=client_name,
                    model_type=llm_mode,
                )
                classified_df = classifier.process_transactions(
                    transactions_df,
                    start_row=start_row,
                    end_row=end_row,
                    resume_from_pass=resume_from_pass,
                )

                if not classified_df.empty:
                    # Save classified transactions
                    output_file = os.path.join(
                        paths["output_paths"]["consolidated_core"]["csv"].replace(
                            "consolidated_core_output.csv",
                            f"{client_name.replace(' ', '_')}_classified_transactions.csv",
                        )
                    )
                    classified_df.to_csv(output_file, index=False)
                    click.echo(
                        f"Successfully classified transactions for client: {client_name}"
                    )
                else:
                    click.echo(
                        f"No transactions were classified for client: {client_name}"
                    )
            except Exception as e:
                click.echo(f"Error: {e}")


if __name__ == "__main__":
    start_menu()
