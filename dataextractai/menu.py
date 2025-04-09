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
from datetime import datetime
from .agents.business_rules_manager import BusinessRulesManager

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
        # Initialize the formatter
        formatter = ExcelReportFormatter()

        # Load transactions
        db = ClientDB()
        transactions_df = db.load_normalized_transactions(client_name)

        if transactions_df.empty:
            click.echo("No transactions found to export.")
            return

        # Check if the user wants to export a specific row range
        export_type = questionary.select(
            "What would you like to export?",
            choices=[
                "All rows (standard Excel)",
                "All rows (with linked formulas)",
                "Specific row range",
            ],
        ).ask()

        if export_type == "Specific row range":
            # Get row range from user
            total_rows = len(transactions_df)
            click.echo(f"Total rows available: {total_rows}")

            start_row = questionary.text(
                "Enter start row (1-based index):",
                validate=lambda x: x.isdigit() and 1 <= int(x) <= total_rows,
            ).ask()

            end_row = questionary.text(
                f"Enter end row ({start_row}-{total_rows}):",
                validate=lambda x: x.isdigit()
                and int(start_row) <= int(x) <= total_rows,
            ).ask()

            if not start_row or not end_row:
                click.echo("Invalid row range provided. Aborting.")
                return

            # Convert to 0-based indexing and filter DataFrame
            start_idx = int(start_row) - 1
            end_idx = int(end_row)
            transactions_df = transactions_df.iloc[start_idx:end_idx]

            click.echo(f"Selected {len(transactions_df)} rows for export.")

        # Set up the export path
        reports_dir = os.path.join("data", "clients", client_name, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_filename = f"{client_name}_transactions_{timestamp}.xlsx"
        export_path = os.path.join(reports_dir, export_filename)

        # Create the report
        use_linked_formulas = export_type == "All rows (with linked formulas)"

        click.echo(
            f"Generating Excel report{' with linked formulas' if use_linked_formulas else ''}..."
        )
        formatter.create_report(
            transactions_df,
            export_path,
            client_name,
            use_linked_formulas=use_linked_formulas,
        )

        click.echo(f"Excel report generated successfully at: {export_path}")
        click.echo(
            f"CSV files are available in: {os.path.join(reports_dir, 'csv_sheets')}"
        )

    except Exception as e:
        click.echo(f"Error generating Excel report: {e}")
        import traceback

        traceback.print_exc()


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


def format_amount(amount):
    """Format amount with appropriate sign and currency symbol."""
    if pd.isna(amount):
        return "N/A"
    return f"${amount:,.2f}" if amount >= 0 else f"-${abs(amount):,.2f}"


def list_transactions(client_name: str):
    """Display a clean, abbreviated view of transactions."""
    try:
        db = ClientDB()
        transactions_df = db.load_normalized_transactions(client_name)

        if transactions_df.empty:
            click.echo("No transactions found.")
            return

        # Get view preferences
        view_type = questionary.select(
            "How would you like to view transactions?",
            choices=[
                "View All",
                "View by Date Range",
                "View by Status",
                "View Recent (Last 10)",
            ],
        ).ask()

        filtered_df = transactions_df.copy()

        if view_type == "View by Date Range":
            start_date = questionary.text(
                "Enter start date (YYYY-MM-DD):",
                default=(filtered_df["transaction_date"].min()),
            ).ask()
            end_date = questionary.text(
                "Enter end date (YYYY-MM-DD):",
                default=(filtered_df["transaction_date"].max()),
            ).ask()
            filtered_df = filtered_df[
                (filtered_df["transaction_date"] >= start_date)
                & (filtered_df["transaction_date"] <= end_date)
            ]
        elif view_type == "View by Status":
            status_choice = questionary.select(
                "Select transactions with status:",
                choices=[
                    "All",
                    "Completed",
                    "Processing",
                    "Pending",
                    "Error",
                    "Skipped",
                    "Force Required",
                ],
            ).ask()

            if status_choice != "All":
                # Get transaction IDs with selected status
                with sqlite3.connect(db.db_path) as conn:
                    cursor = conn.execute(
                        """
                        SELECT transaction_id 
                        FROM transaction_status 
                        WHERE client_id = ? 
                        AND (pass_1_status = ? OR pass_2_status = ? OR pass_3_status = ?)
                        """,
                        (
                            db.get_client_id(client_name),
                            status_choice.lower(),
                            status_choice.lower(),
                            status_choice.lower(),
                        ),
                    )
                    status_transaction_ids = [row[0] for row in cursor.fetchall()]
                filtered_df = filtered_df[
                    filtered_df["transaction_id"].isin(status_transaction_ids)
                ]
        elif view_type == "View Recent (Last 10)":
            filtered_df = filtered_df.tail(10)

        # Get sort preference
        sort_by = questionary.select(
            "Sort transactions by:",
            choices=[
                "Date (Newest First)",
                "Date (Oldest First)",
                "Transaction ID (Ascending)",
                "Transaction ID (Descending)",
                "Amount (Highest First)",
                "Amount (Lowest First)",
            ],
        ).ask()

        # Apply sorting
        if sort_by == "Date (Newest First)":
            filtered_df = filtered_df.sort_values("transaction_date", ascending=False)
        elif sort_by == "Date (Oldest First)":
            filtered_df = filtered_df.sort_values("transaction_date", ascending=True)
        elif sort_by == "Transaction ID (Ascending)":
            filtered_df = filtered_df.sort_values("transaction_id", ascending=True)
        elif sort_by == "Transaction ID (Descending)":
            filtered_df = filtered_df.sort_values("transaction_id", ascending=False)
        elif sort_by == "Amount (Highest First)":
            filtered_df = filtered_df.sort_values("amount", ascending=False)
        elif sort_by == "Amount (Lowest First)":
            filtered_df = filtered_df.sort_values("amount", ascending=True)

        # Display transactions in a clean format
        click.echo("\nTransactions:")
        click.echo("=" * 150)

        # Header format
        header = "{:<5} {:<12} {:<12} {:<30} {:<15} {:<20} {:<8} {:<15} {:<15} {:<10}".format(
            "ID",
            "Date",
            "Amount",
            "Description",
            "Payee",
            "Category",
            "Bus %",
            "Tax Cat",
            "Class",
            "Status",
        )
        click.echo(header)
        click.echo("-" * 150)

        # Get status information for color coding
        status_info = {}
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    transaction_id,
                    pass_1_status,
                    pass_2_status,
                    pass_3_status
                FROM transaction_status
                WHERE client_id = ?
                """,
                (db.get_client_id(client_name),),
            )
            for row in cursor:
                status_info[row[0]] = {
                    "pass_1": row[1],
                    "pass_2": row[2],
                    "pass_3": row[3],
                }

        # Status colors
        status_colors = {
            "completed": "green",
            "processing": "yellow",
            "pending": "blue",
            "error": "red",
            "skipped": "magenta",
            "force_required": "bright_red",
        }

        # Row format with color based on status
        for _, row in filtered_df.iterrows():
            status = status_info.get(row["transaction_id"], {})

            # Determine row color based on worst status
            worst_status = "completed"  # default
            for pass_status in status.values():
                if pass_status in ["error", "force_required"]:
                    worst_status = pass_status
                    break
                elif pass_status == "processing":
                    worst_status = "processing"
                elif pass_status == "pending" and worst_status not in [
                    "error",
                    "force_required",
                ]:
                    worst_status = "pending"

            color = status_colors.get(worst_status, "white")

            # Format row data
            row_str = "{:<5} {:<12} {:<12} {:<30} {:<15} {:<20} {:<8} {:<15} {:<15} {:<10}".format(
                row["transaction_id"],
                row["transaction_date"],
                format_amount(row["amount"]),
                (
                    (row["description"][:27] + "...")
                    if len(str(row["description"])) > 30
                    else str(row["description"])
                ),
                (
                    (row.get("payee", "Unclassified")[:12] + "...")
                    if len(str(row.get("payee", "Unclassified"))) > 15
                    else str(row.get("payee", "Unclassified"))
                ),
                (
                    (row.get("category", "Unclassified")[:17] + "...")
                    if len(str(row.get("category", "Unclassified"))) > 20
                    else str(row.get("category", "Unclassified"))
                ),
                f"{row.get('business_percentage', 'N/A')}%",
                str(row.get("tax_category", "N/A")),
                str(row.get("classification", "N/A")),
                worst_status,
            )

            click.echo(click.style(row_str, fg=color))

        click.echo(f"\nTotal Transactions: {len(filtered_df)}")

        # Show legend
        click.echo("\nStatus Colors:")
        for status, color in status_colors.items():
            click.echo(click.style(f"  {status}", fg=color))

        # Option to view detailed information for a specific transaction
        if questionary.confirm(
            "\nWould you like to view detailed information for a specific transaction?"
        ).ask():
            while True:
                transaction_id = questionary.text(
                    "Enter transaction ID (or leave empty to finish):"
                ).ask()
                if not transaction_id:
                    break

                # Get full transaction details
                transaction = filtered_df[
                    filtered_df["transaction_id"] == transaction_id
                ]
                if not transaction.empty:
                    click.echo("\nDetailed Transaction Information:")
                    click.echo("=" * 80)

                    # Basic Information
                    click.echo("\nBasic Information:")
                    click.echo(f"ID: {transaction_id}")
                    click.echo(f"Date: {transaction.iloc[0]['transaction_date']}")
                    click.echo(
                        f"Amount: {format_amount(transaction.iloc[0]['amount'])}"
                    )
                    click.echo(f"Description: {transaction.iloc[0]['description']}")

                    # Pass 1 - Payee Information
                    click.echo("\nPayee Information (Pass 1):")
                    click.echo(f"Payee: {transaction.iloc[0].get('payee', 'N/A')}")
                    click.echo(
                        f"Confidence: {transaction.iloc[0].get('payee_confidence', 'N/A')}"
                    )
                    click.echo(
                        f"Reasoning: {transaction.iloc[0].get('payee_reasoning', 'N/A')}"
                    )

                    # Pass 2 - Category Information
                    click.echo("\nCategory Information (Pass 2):")
                    click.echo(
                        f"Category: {transaction.iloc[0].get('category', 'N/A')}"
                    )
                    click.echo(
                        f"Confidence: {transaction.iloc[0].get('category_confidence', 'N/A')}"
                    )
                    click.echo(
                        f"Reasoning: {transaction.iloc[0].get('category_reasoning', 'N/A')}"
                    )

                    # Pass 3 - Classification Information
                    click.echo("\nClassification Information (Pass 3):")
                    click.echo(
                        f"Classification: {transaction.iloc[0].get('classification', 'N/A')}"
                    )
                    click.echo(
                        f"Business %: {transaction.iloc[0].get('business_percentage', 'N/A')}%"
                    )
                    click.echo(
                        f"Tax Category: {transaction.iloc[0].get('tax_category', 'N/A')}"
                    )
                    click.echo(
                        f"Tax Implications: {transaction.iloc[0].get('tax_implications', 'N/A')}"
                    )
                    click.echo(
                        f"Confidence: {transaction.iloc[0].get('classification_confidence', 'N/A')}"
                    )
                    click.echo(
                        f"Reasoning: {transaction.iloc[0].get('classification_reasoning', 'N/A')}"
                    )

                    # Processing Status
                    status = status_info.get(transaction_id, {})
                    click.echo("\nProcessing Status:")
                    click.echo(f"Pass 1 (Payee): {status.get('pass_1', 'N/A')}")
                    click.echo(f"Pass 2 (Category): {status.get('pass_2', 'N/A')}")
                    click.echo(
                        f"Pass 3 (Classification): {status.get('pass_3', 'N/A')}"
                    )
                else:
                    click.echo("Transaction not found.")

    except Exception as e:
        click.echo(f"Error listing transactions: {e}")
        import traceback

        traceback.print_exc()


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
                "\n--- Processing ---",
                "Process All Transactions (Fast)",
                "Process All Transactions (Precise)",
                "Process Row Range (Fast)",
                "Process Row Range (Precise)",
                "Resume Processing from Pass",
                "Reprocess Failed Transactions",
                "Reprocess Specific Pass for All",
                "\n--- Data Management & Review ---",
                "List Transactions",
                "View Transaction Status",
                "Reset Transaction Status",
                "Sync Transactions to Database",
                "Export to Excel Report (+CSVs)",
                "Upload to Google Sheets",
                "Review Pass 2 Results",
                "Exit",
            ],
        ).ask()

        if action == "Exit" or action is None:
            break

        if action == "List Clients":
            list_clients()
            continue

        # --- Client Selection (for most actions) ---
        if not action.startswith("---") and action != "Exit":
            clients = get_client_list()
            if not clients:
                click.echo("No clients found. Please create a client first.")
                continue
            client_name = questionary.select("Select a client:", choices=clients).ask()
            if client_name is None:
                continue  # Handle user cancelling

        # --- Menu Actions ---
        if action == "Create/Update Business Profile":
            try:
                create_or_update_profile(client_name)
            except Exception as e:
                click.echo(f"Error updating business profile: {e}")

        elif action == "Run Parsers":
            try:
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

        elif action.startswith("Process All Transactions"):
            try:
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)
                if transactions_df.empty:
                    click.echo("No transactions found to process.")
                    continue

                model_type = "PRECISE" if "Precise" in action else "FAST"
                force_reprocessing = questionary.confirm(
                    "Force reprocessing ALL transactions (ignore existing classifications)?",
                    default=False,
                ).ask()

                click.echo(f"\nInitializing classifier using {model_type} model...")
                os.environ["OPENAI_MODEL_TYPE"] = model_type
                classifier = TransactionClassifier(client_name)
                click.echo(
                    f"Processing ALL transactions (Force Reprocessing: {force_reprocessing})..."
                )
                classifier.process_transactions(
                    transactions_df, force_process=force_reprocessing
                )
                click.echo("\nProcessing complete for all transactions.")
            except Exception as e:
                click.echo(f"Error processing all transactions: {e}")
                import traceback

                traceback.print_exc()

        elif action == "Process Row Range (Fast)":
            process_transactions_by_range(
                client_name, "FAST"
            )  # Calls function with prompt
        elif action == "Process Row Range (Precise)":
            process_transactions_by_range(
                client_name, "PRECISE"
            )  # Calls function with prompt

        elif action == "Resume Processing from Pass":
            try:
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)
                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                pass_num_str = questionary.select(
                    "Resume from Pass:", choices=["1", "2", "3"]
                ).ask()
                if not pass_num_str:
                    continue
                pass_num = int(pass_num_str)

                force_reprocessing = questionary.confirm(
                    f"Force reprocessing from Pass {pass_num} onwards?", default=False
                ).ask()
                model_type = questionary.select(
                    "Select model type:", choices=["FAST", "PRECISE"]
                ).ask()
                if not model_type:
                    continue

                click.echo(f"\nInitializing classifier using {model_type} model...")
                os.environ["OPENAI_MODEL_TYPE"] = model_type
                classifier = TransactionClassifier(client_name)
                click.echo(
                    f"Resuming processing from Pass {pass_num} (Force: {force_reprocessing})..."
                )
                classifier.process_transactions(
                    transactions_df, force_process=force_reprocessing
                )
                click.echo("\nResumed processing complete.")
            except Exception as e:
                click.echo(f"Error resuming processing: {e}")
                import traceback

                traceback.print_exc()

        elif action == "Reprocess Failed Transactions":
            try:
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)
                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                failed_ids = db.get_transactions_by_status(client_name, "error")
                if not failed_ids:
                    click.echo("No transactions with status 'error' found.")
                    continue

                click.echo(f"Found {len(failed_ids)} transactions with status 'error'.")
                model_type = questionary.select(
                    "Select model type:", choices=["FAST", "PRECISE"]
                ).ask()
                if not model_type:
                    continue

                if questionary.confirm(
                    f"Reprocess these {len(failed_ids)} transactions (will force reclassification)?"
                ).ask():
                    click.echo(f"\nInitializing classifier using {model_type} model...")
                    os.environ["OPENAI_MODEL_TYPE"] = model_type
                    classifier = TransactionClassifier(client_name)
                    failed_df = transactions_df[
                        transactions_df["transaction_id"].isin(failed_ids)
                    ]
                    click.echo(
                        f"Reprocessing {len(failed_df)} failed transactions (Forced)..."
                    )
                    classifier.process_transactions(
                        transactions_df, force_process=True
                    )  # Force is implicit here
                    click.echo("\nReprocessing of failed transactions complete.")
                else:
                    click.echo("Reprocessing cancelled.")
            except Exception as e:
                click.echo(f"Error reprocessing failed transactions: {e}")
                import traceback

                traceback.print_exc()

        elif action == "Reprocess Specific Pass for All":
            try:
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)
                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                pass_num_str = questionary.select(
                    "Which Pass to reprocess for ALL transactions?",
                    choices=["1", "2", "3"],
                ).ask()
                if not pass_num_str:
                    continue
                pass_num = int(pass_num_str)

                model_type = questionary.select(
                    "Select model type:", choices=["FAST", "PRECISE"]
                ).ask()
                if not model_type:
                    continue

                if questionary.confirm(
                    f"This will FORCE re-run Pass {pass_num} for ALL transactions. Continue?"
                ).ask():
                    click.echo(f"\nInitializing classifier using {model_type} model...")
                    os.environ["OPENAI_MODEL_TYPE"] = model_type
                    classifier = TransactionClassifier(client_name)
                    click.echo(
                        f"Reprocessing Pass {pass_num} for ALL transactions (Forced)..."
                    )
                    # We use resume_from_pass to effectively target the specific pass, and force=True
                    classifier.process_transactions(transactions_df, force_process=True)
                    click.echo(f"\nReprocessing of Pass {pass_num} complete.")
                else:
                    click.echo("Reprocessing cancelled.")
            except Exception as e:
                click.echo(f"Error reprocessing pass: {e}")
                import traceback

                traceback.print_exc()

        elif action == "List Transactions":
            list_transactions(client_name)

        elif action == "View Transaction Status":
            try:
                db = ClientDB()
                db.display_transaction_status_summary(client_name)
                # Add option to view details if needed
            except Exception as e:
                click.echo(f"Error viewing transaction status: {e}")

        elif action == "Reset Transaction Status":
            try:
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)
                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue
                transaction_id = questionary.text(
                    "Enter transaction ID to reset (or leave blank to cancel):"
                ).ask()
                if not transaction_id:
                    continue

                current_status = db.get_transaction_status_details(
                    client_name, transaction_id
                )
                if not current_status:
                    click.echo("Transaction ID not found.")
                    continue

                click.echo("Current Status:")
                for p, details in current_status.items():
                    click.echo(
                        f"  {p.upper()}: {details['status']} (Error: {details['error'] or 'None'}) @ {details['processed_at'] or 'N/A'}"
                    )

                passes_to_reset = questionary.checkbox(
                    "Select passes to reset to 'pending':",
                    choices=["Pass 1", "Pass 2", "Pass 3"],
                ).ask()
                if not passes_to_reset:
                    click.echo("No passes selected.")
                    continue

                if questionary.confirm(
                    f"Reset status for {transaction_id} for {', '.join(passes_to_reset)}?"
                ).ask():
                    db.reset_transaction_status(
                        client_name, transaction_id, [p[5:6] for p in passes_to_reset]
                    )
                    click.echo("Transaction status reset.")
                else:
                    click.echo("Reset cancelled.")
            except Exception as e:
                click.echo(f"Error resetting status: {e}")

        elif action == "Sync Transactions to Database":
            try:
                sync_transactions_to_db(client_name)
            except Exception as e:
                click.echo(f"Error syncing transactions: {e}")

        elif action == "Export to Excel Report (+CSVs)":
            handle_excel_export(client_name)

        elif action == "Upload to Google Sheets":
            handle_sheets_menu(client_name)

        elif action == "Review Pass 2 Results":
            review_pass2_results(client_name)


def review_pass2_results(client_name: str):
    """Review and adjust Pass 2 results before proceeding to Pass 3."""
    db = ClientDB()
    rules_manager = BusinessRulesManager(client_name)

    while True:
        action = questionary.select(
            "Review Options:",
            choices=[
                "View by Category",
                "View by Business Percentage",
                "View by Payee",
                "View Unreviewed Transactions",
                "Batch Update Business Percentage",
                "Batch Update Category",
                "Add Review Notes",
                "Mark as Reviewed",
                "Generate Business Rules",
                "View/Edit Business Rules",
                "Apply Business Rules",
                "Back to Main Menu",
            ],
        ).ask()

        if action == "Back to Main Menu":
            break

        elif action == "Generate Business Rules":
            # Get all transactions
            transactions = db.load_normalized_transactions(client_name)
            if transactions.empty:
                click.echo("No transactions found.")
                continue

            # Convert DataFrame to list of dictionaries
            transactions_list = transactions.to_dict("records")

            # Generate rules
            click.echo("\nAnalyzing transactions and generating business rules...")
            rules = rules_manager.analyze_and_generate_rules(transactions_list)

            # Display generated rules
            click.echo("\nGenerated Business Rules:")
            for rule in rules:
                click.echo("\n" + "=" * 50)
                click.echo(f"Rule: {rule['rule_name']}")
                click.echo(f"Type: {rule['rule_type']}")
                click.echo(f"Description: {rule['rule_description']}")
                click.echo(f"Confidence: {rule['ai_confidence']}")
                click.echo(f"Reasoning: {rule['ai_reasoning']}")
                click.echo("Conditions:")
                for condition in rule["conditions"]:
                    click.echo(
                        f"  - {condition['field']} {condition['operator']} {condition['value']}"
                    )
                click.echo("Actions:")
                for action in rule["actions"]:
                    click.echo(f"  - Set {action['field']} to {action['value']}")

        elif action == "View/Edit Business Rules":
            rules = db.get_business_rules(client_name)
            if not rules:
                click.echo("No business rules found.")
                continue

            while True:
                rule_action = questionary.select(
                    "Rule Management:",
                    choices=[
                        "View All Rules",
                        "Edit Rule",
                        "Deactivate Rule",
                        "Back to Review Menu",
                    ],
                ).ask()

                if rule_action == "Back to Review Menu":
                    break

                elif rule_action == "View All Rules":
                    for rule in rules:
                        click.echo("\n" + "=" * 50)
                        click.echo(f"Rule: {rule['rule_name']}")
                        click.echo(f"Type: {rule['rule_type']}")
                        click.echo(f"Description: {rule['rule_description']}")
                        click.echo(f"Active: {'Yes' if rule['is_active'] else 'No'}")
                        click.echo(
                            f"AI Generated: {'Yes' if rule['ai_generated'] else 'No'}"
                        )
                        if rule["ai_generated"]:
                            click.echo(f"AI Confidence: {rule['ai_confidence']}")
                            click.echo(f"AI Reasoning: {rule['ai_reasoning']}")

                elif rule_action == "Deactivate Rule":
                    rule_name = questionary.select(
                        "Select rule to deactivate:",
                        choices=[r["rule_name"] for r in rules if r["is_active"]],
                    ).ask()
                    if rule_name:
                        db.deactivate_business_rule(client_name, rule_name)
                        click.echo(f"Deactivated rule: {rule_name}")

        elif action == "Apply Business Rules":
            # Get transactions to apply rules to
            filter_type = questionary.select(
                "Apply rules to:",
                choices=[
                    "All Transactions",
                    "Unreviewed Transactions",
                    "Selected Category",
                    "Selected Payee",
                    "Selected IDs",
                ],
            ).ask()

            transactions_to_update = get_filtered_transactions(
                db, client_name, filter_type
            )
            if not transactions_to_update:
                click.echo("No transactions selected.")
                continue

            # Apply rules and show preview
            click.echo("\nPreviewing changes:")
            changes = []
            for txn in transactions_to_update:
                modified_txn = rules_manager.apply_rules_to_transaction(txn)
                if modified_txn != txn:
                    changes.append((txn, modified_txn))

            if not changes:
                click.echo("No changes would be made by applying rules.")
                continue

            # Show preview of changes
            for original, modified in changes:
                click.echo("\n" + "-" * 50)
                click.echo(f"Transaction ID: {original['transaction_id']}")
                click.echo(f"Date: {original['transaction_date']}")
                click.echo(f"Description: {original['description']}")
                click.echo("\nChanges:")
                for key in modified:
                    if key in original and modified[key] != original[key]:
                        click.echo(f"  {key}: {original[key]} -> {modified[key]}")

            # Confirm and apply changes
            if questionary.confirm("Apply these changes?").ask():
                for original, modified in changes:
                    # Update transaction with modified values
                    update_data = {
                        k: v
                        for k, v in modified.items()
                        if k in original and v != original[k]
                    }
                    db.update_transaction_classification(
                        original["transaction_id"], update_data
                    )
                click.echo(f"Successfully updated {len(changes)} transactions")

        elif action == "View by Category":
            category = questionary.select(
                "Select category to view:",
                choices=sorted(list(set(db.get_all_categories(client_name)))),
            ).ask()

            transactions = db.load_transactions_by_category(client_name, category)
            display_transactions_for_review(transactions)

            # After displaying transactions, offer to generate rules
            if questionary.confirm(
                "\nWould you like to generate business rules based on these transactions?"
            ).ask():
                suggested_rules = rules_manager.get_rule_suggestions(transactions[0])

                click.echo("\nSuggested Business Rules:")
                for rule in suggested_rules:
                    click.echo("\n" + "=" * 50)
                    click.echo(f"Rule: {rule['rule_name']}")
                    click.echo(f"Description: {rule['rule_description']}")
                    click.echo(f"Confidence: {rule['ai_confidence']}")
                    click.echo(f"Reasoning: {rule['ai_reasoning']}")

                    if questionary.confirm("Would you like to save this rule?").ask():
                        db.save_business_rule(client_name, rule)
                        click.echo("Rule saved successfully")

        elif action == "View by Business Percentage":
            percentage = questionary.text(
                "Enter business percentage to view (0-100):",
                validate=lambda x: x.isdigit() and 0 <= int(x) <= 100,
            ).ask()

            transactions = db.load_transactions_by_business_percentage(
                client_name, int(percentage)
            )
            display_transactions_for_review(transactions)

        elif action == "View by Payee":
            payee = questionary.select(
                "Select payee to view:",
                choices=sorted(list(set(db.get_all_payees(client_name)))),
            ).ask()

            transactions = db.load_transactions_by_payee(client_name, payee)
            display_transactions_for_review(transactions)

        elif action == "Batch Update Business Percentage":
            # Get filter criteria
            filter_type = questionary.select(
                "Filter transactions by:", choices=["Category", "Payee", "Selected IDs"]
            ).ask()

            # Get transactions based on filter
            transactions_to_update = get_filtered_transactions(
                db, client_name, filter_type
            )

            # Get new percentage
            new_percentage = questionary.text(
                "Enter new business percentage (0-100):",
                validate=lambda x: x.isdigit() and 0 <= int(x) <= 100,
            ).ask()

            # Confirm update
            if questionary.confirm(
                f"Update {len(transactions_to_update)} transactions to {new_percentage}% business?"
            ).ask():
                db.batch_update_business_percentage(
                    client_name,
                    [t["transaction_id"] for t in transactions_to_update],
                    int(new_percentage),
                )
                click.echo("Successfully updated business percentage")

        elif action == "Add Review Notes":
            # Similar structure to batch update, but for adding notes
            pass

        elif action == "Mark as Reviewed":
            # Similar structure to batch update, but for marking as reviewed
            pass


def display_transactions_for_review(transactions):
    """Display transactions in a review-friendly format."""
    click.echo("\nTransactions for Review:")
    click.echo("=" * 120)

    header = "{:<5} {:<12} {:<12} {:<30} {:<15} {:<15} {:<10} {:<15}".format(
        "ID",
        "Date",
        "Amount",
        "Description",
        "Payee",
        "Category",
        "Bus %",
        "Review Status",
    )
    click.echo(header)
    click.echo("-" * 120)

    for t in transactions:
        row = "{:<5} {:<12} {:<12} {:<30} {:<15} {:<15} {:<10} {:<15}".format(
            t["transaction_id"],
            t["transaction_date"],
            f"${t['amount']:.2f}",
            t["description"][:30],
            t["payee"][:15],
            t["category"][:15],
            f"{t['business_percentage']}%",
            "✓" if t["is_reviewed"] else "",
        )
        click.echo(row)


def get_filtered_transactions(db, client_name, filter_type):
    """Get transactions based on filter criteria."""
    if filter_type == "Category":
        category = questionary.select(
            "Select category:",
            choices=sorted(list(set(db.get_all_categories(client_name)))),
        ).ask()
        return db.load_transactions_by_category(client_name, category)

    elif filter_type == "Payee":
        payee = questionary.select(
            "Select payee:", choices=sorted(list(set(db.get_all_payees(client_name))))
        ).ask()
        return db.load_transactions_by_payee(client_name, payee)

    elif filter_type == "Selected IDs":
        transaction_ids = []
        while True:
            transaction_id = questionary.text(
                "Enter transaction ID (or leave empty to finish):"
            ).ask()
            if not transaction_id:
                break
            transaction_ids.append(transaction_id)
        return db.load_transactions_by_ids(client_name, transaction_ids)


def manage_categories(
    existing_categories: List[str], profile_manager: ClientProfileManager
) -> List[str]:
    """Manage custom categories with options to add, edit, or delete."""
    categories = existing_categories.copy()

    # Get current mappings and keywords from profile
    profile = profile_manager._load_profile()
    category_mapping = profile.get("category_mapping", {}) if profile else {}
    industry_keywords = profile.get("industry_keywords", {}) if profile else {}

    while True:
        action = questionary.select(
            "Profile Management:",
            choices=[
                "View Categories and 6A Mappings",
                "Add Custom Category",
                "Edit Custom Category",
                "Delete Custom Category",
                "Manage Industry Keywords",
                "Done",
            ],
        ).ask()

        if action == "Done":
            return categories

        elif action == "Manage Industry Keywords":
            while True:
                keyword_action = questionary.select(
                    "Industry Keywords Management:",
                    choices=[
                        "View Keywords",
                        "Add Keyword",
                        "Edit Keyword",
                        "Delete Keyword",
                        "Regenerate All Keywords",
                        "Back",
                    ],
                ).ask()

                if keyword_action == "Back":
                    break

                elif keyword_action == "View Keywords":
                    if not industry_keywords:
                        click.echo("No industry keywords defined.")
                    else:
                        click.echo("\nIndustry Keywords and Weights:")
                        # Sort by weight descending
                        sorted_keywords = sorted(
                            industry_keywords.items(), key=lambda x: x[1], reverse=True
                        )
                        for keyword, weight in sorted_keywords:
                            click.echo(f"- {keyword}: {weight:.2f}")

                elif keyword_action == "Add Keyword":
                    new_keyword = questionary.text("Enter new keyword:").ask()
                    if new_keyword and new_keyword not in industry_keywords:
                        weight = questionary.select(
                            "Select keyword weight:",
                            choices=[
                                "0.95 - Essential to business identity",
                                "0.90 - Primary business activity",
                                "0.85 - Common business element",
                                "0.80 - Supporting activity",
                                "0.75 - Related concept",
                            ],
                        ).ask()
                        weight_value = float(weight.split(" - ")[0])
                        industry_keywords[new_keyword] = weight_value
                        click.echo(
                            f"Added keyword: {new_keyword} with weight {weight_value}"
                        )

                elif keyword_action == "Edit Keyword":
                    if not industry_keywords:
                        click.echo("No keywords to edit.")
                        continue
                    keyword_to_edit = questionary.select(
                        "Select keyword to edit:",
                        choices=list(industry_keywords.keys()) + ["Cancel"],
                    ).ask()
                    if keyword_to_edit != "Cancel":
                        edit_what = questionary.checkbox(
                            "What would you like to edit?",
                            choices=["Keyword Text", "Weight"],
                        ).ask()

                        if "Keyword Text" in edit_what:
                            new_text = questionary.text(
                                "Enter new text:", default=keyword_to_edit
                            ).ask()
                            if new_text:
                                weight = industry_keywords.pop(keyword_to_edit)
                                industry_keywords[new_text] = weight
                                click.echo(
                                    f"Updated keyword text: {keyword_to_edit} -> {new_text}"
                                )

                        if "Weight" in edit_what:
                            current_weight = industry_keywords[keyword_to_edit]
                            new_weight = questionary.select(
                                f"Select new weight for '{keyword_to_edit}' (currently: {current_weight}):",
                                choices=[
                                    "0.95 - Essential to business identity",
                                    "0.90 - Primary business activity",
                                    "0.85 - Common business element",
                                    "0.80 - Supporting activity",
                                    "0.75 - Related concept",
                                ],
                            ).ask()
                            weight_value = float(new_weight.split(" - ")[0])
                            industry_keywords[keyword_to_edit] = weight_value
                            click.echo(
                                f"Updated weight for {keyword_to_edit}: {weight_value}"
                            )

                elif keyword_action == "Delete Keyword":
                    if not industry_keywords:
                        click.echo("No keywords to delete.")
                        continue
                    keyword_to_delete = questionary.select(
                        "Select keyword to delete:",
                        choices=list(industry_keywords.keys()) + ["Cancel"],
                    ).ask()
                    if keyword_to_delete != "Cancel":
                        del industry_keywords[keyword_to_delete]
                        click.echo(f"Deleted keyword: {keyword_to_delete}")

                elif keyword_action == "Regenerate All Keywords":
                    if questionary.confirm(
                        "This will replace all existing keywords. Continue?"
                    ).ask():
                        # Get business type and description from profile
                        business_type = profile.get("business_type", "")
                        business_description = profile.get("business_description", "")
                        if business_type and business_description:
                            industry_keywords = (
                                profile_manager._generate_industry_keywords(
                                    business_type, business_description
                                )
                            )
                            click.echo("Keywords regenerated successfully.")
                        else:
                            click.echo(
                                "Error: Business type and description required to regenerate keywords."
                            )

                # Update profile with new keywords
                if profile:
                    profile["industry_keywords"] = industry_keywords
                    profile_manager._save_profile(profile)

        elif action == "View Categories and 6A Mappings":
            if not categories:
                click.echo("No custom categories defined.")
            else:
                click.echo("\nCustom Categories and their Schedule 6A Mappings:")
                for i, cat in enumerate(categories, 1):
                    mapped_to = category_mapping.get(cat, "Not mapped")
                    click.echo(f"{i}. {cat} -> Maps to: {mapped_to}")

        elif action == "Add Custom Category":
            # First show available 6A categories
            click.echo("\nAvailable Schedule 6A Categories:")
            schedule_6a = [
                "Advertising",
                "Car and truck expenses",
                "Commissions and fees",
                "Contract labor",
                "Depletion",
                "Employee benefit programs",
                "Insurance (other than health)",
                "Interest (mortgage/other)",
                "Legal and professional services",
                "Office expenses",
                "Pension and profit-sharing plans",
                "Rent or lease (vehicles/equipment/other)",
                "Repairs and maintenance",
                "Supplies",
                "Taxes and licenses",
                "Travel, meals, and entertainment",
                "Utilities",
                "Wages",
                "Other expenses",
            ]
            for cat in schedule_6a:
                click.echo(f"- {cat}")

            new_cat = questionary.text("Enter new custom category:").ask()
            if new_cat and new_cat not in categories:
                # Select which 6A category this maps to
                mapped_to = questionary.select(
                    f"Which Schedule 6A category should '{new_cat}' map to?",
                    choices=schedule_6a,
                ).ask()

                categories.append(new_cat)
                category_mapping[new_cat] = mapped_to
                click.echo(f"Added category: {new_cat} -> Maps to: {mapped_to}")

        elif action == "Edit Custom Category":
            if not categories:
                click.echo("No categories to edit.")
                continue
            cat_to_edit = questionary.select(
                "Select category to edit:", choices=categories + ["Cancel"]
            ).ask()
            if cat_to_edit != "Cancel":
                # Allow editing name and/or mapping
                edit_what = questionary.checkbox(
                    "What would you like to edit?",
                    choices=["Category Name", "6A Mapping"],
                ).ask()

                if "Category Name" in edit_what:
                    new_name = questionary.text(
                        "Enter new name:", default=cat_to_edit
                    ).ask()
                    if new_name:
                        idx = categories.index(cat_to_edit)
                        categories[idx] = new_name
                        # Update mapping
                        if cat_to_edit in category_mapping:
                            category_mapping[new_name] = category_mapping.pop(
                                cat_to_edit
                            )
                        click.echo(
                            f"Updated category name: {cat_to_edit} -> {new_name}"
                        )

                if "6A Mapping" in edit_what:
                    current_mapping = category_mapping.get(cat_to_edit, "Not mapped")
                    new_mapping = questionary.select(
                        f"Select new Schedule 6A mapping for '{cat_to_edit}' (currently: {current_mapping}):",
                        choices=schedule_6a,
                    ).ask()
                    category_mapping[cat_to_edit] = new_mapping
                    click.echo(f"Updated mapping: {cat_to_edit} -> {new_mapping}")

        elif action == "Delete Custom Category":
            if not categories:
                click.echo("No categories to delete.")
                continue
            cat_to_delete = questionary.select(
                "Select category to delete:", choices=categories + ["Cancel"]
            ).ask()
            if cat_to_delete != "Cancel":
                categories.remove(cat_to_delete)
                # Remove from mapping
                if cat_to_delete in category_mapping:
                    del category_mapping[cat_to_delete]
                click.echo(f"Deleted category: {cat_to_delete}")

    # Update profile with new mappings
    if profile:
        profile["category_mapping"] = category_mapping
        profile_manager._save_profile(profile)

    return categories


def create_or_update_profile(client_name: str):
    """Create or update a business profile."""
    try:
        # Initialize profile manager
        profile_manager = ClientProfileManager(client_name)

        # Load existing profile
        existing_profile = profile_manager._load_profile()

        # Use existing values as defaults
        default_business_type = (
            existing_profile.get("business_type", "") if existing_profile else ""
        )
        default_description = (
            existing_profile.get("business_description", "") if existing_profile else ""
        )
        default_categories = (
            existing_profile.get("custom_categories", []) if existing_profile else []
        )

        # Get new values with defaults
        business_type = questionary.text(
            f"Business Type (current: {default_business_type or 'Not set'}):",
            default=default_business_type,
        ).ask()

        business_description = questionary.text(
            f"Business Description (current: {default_description or 'Not set'}):",
            default=default_description,
        ).ask()

        # Handle categories using the new management function
        click.echo("\nCustom Categories Management")
        click.echo("These are sub-categories that map to Schedule 6A categories.")
        categories = manage_categories(default_categories, profile_manager)

        # Check if anything has changed
        has_changes = (
            business_type != default_business_type
            or business_description != default_description
            or sorted(categories) != sorted(default_categories)
        )

        if has_changes:
            # Create or update profile with AI enhancement
            click.echo("\nChanges detected. Regenerating AI-enhanced profile...")
            profile = profile_manager.create_or_update_profile(
                business_type=business_type,
                business_description=business_description,
                custom_categories=categories,
            )
        else:
            click.echo("\nNo changes detected. Using existing profile...")
            profile = existing_profile

        # Show the enhanced profile
        click.echo("\nProfile Details:")
        click.echo(f"Business Type: {profile['business_type']}")
        click.echo(f"Description: {profile['business_description']}")
        click.echo("\nCustom Categories and their Schedule 6A Mappings:")
        for cat in profile["custom_categories"]:
            mapped_to = profile.get("category_mapping", {}).get(cat, "Not mapped")
            click.echo(f"- {cat} -> Maps to: {mapped_to}")

        # Display industry keywords with weights
        click.echo("\nIndustry Keywords:")
        industry_keywords = profile.get("industry_keywords", {})
        if industry_keywords:
            # Sort by weight descending
            sorted_keywords = sorted(
                industry_keywords.items(), key=lambda x: x[1], reverse=True
            )
            for keyword, weight in sorted_keywords:
                click.echo(f"- {keyword}: {weight:.2f}")

            # Offer to edit keywords if they exist
            if questionary.confirm(
                "\nWould you like to edit the industry keywords?"
            ).ask():
                profile = (
                    profile_manager._load_profile()
                )  # Reload to ensure we have latest
                categories = manage_categories(
                    profile.get("custom_categories", []), profile_manager
                )
                # No need to regenerate AI profile here since we're just editing keywords
        else:
            click.echo("No industry keywords generated")

        click.echo("\nIndustry Insights:")
        click.echo(profile.get("industry_insights", ""))
        click.echo("\nBusiness Context:")
        click.echo(profile.get("business_context", ""))

    except Exception as e:
        click.echo(f"Error updating business profile: {e}")


def process_transactions_by_range(client_name: str, model_type: str):
    """Process transactions within a specific row range using the specified model."""
    try:
        # Load transactions from the database
        db = ClientDB()
        transactions_df = db.load_normalized_transactions(client_name)
        if transactions_df.empty:
            click.echo("No transactions found to process.")
            return

        total_rows = len(transactions_df)
        click.echo(f"Total transactions found: {total_rows}")

        # Get row range from user
        start_row = questionary.text(
            "Enter start row number (1-based index):",
            validate=lambda x: x.isdigit() and 1 <= int(x) <= total_rows,
        ).ask()
        end_row = questionary.text(
            f"Enter end row number ({start_row}-{total_rows}):",
            validate=lambda x: x.isdigit() and int(start_row) <= int(x) <= total_rows,
        ).ask()

        if not start_row or not end_row:
            click.echo("Invalid row range provided. Aborting.")
            return

        start_row_idx = int(start_row) - 1  # Convert to 0-based index
        end_row_idx = int(end_row)  # end_row is exclusive for slicing

        # *** ADD CONFIRMATION STEP ***
        force_reprocessing = questionary.confirm(
            "Force reprocessing (ignore existing classifications)?", default=False
        ).ask()

        # Initialize classifier
        click.echo(f"\nInitializing classifier using {model_type} model...")
        # Set environment variable for model selection within classifier
        os.environ["OPENAI_MODEL_TYPE"] = model_type
        classifier = TransactionClassifier(client_name)

        # Process the selected range
        click.echo(
            f"Processing rows {start_row} to {end_row} (Force Reprocessing: {force_reprocessing})..."
        )
        classifier.process_transactions(
            transactions_df,
            force_process=force_reprocessing,
            start_row=start_row_idx,
            end_row=end_row_idx,
        )

        click.echo("\nProcessing complete for the selected range.")

    except Exception as e:
        click.echo(f"Error processing transactions by range: {e}")
        import traceback

        traceback.print_exc()  # Print traceback for detailed debugging


if __name__ == "__main__":
    start_menu()
