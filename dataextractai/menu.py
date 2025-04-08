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
                "\nTransaction Management:",
                "List Transactions",
                "View Transaction Status",
                "Force Process Transactions",
                "Reset Transaction Status",
                "Reprocess Failed Transactions",
                "Reprocess Pass for All Transactions",
                "\nData Management:",
                "Sync Transactions to Database",
                "Purge Classification Cache",
                "Export to Excel Report",
                "Upload to Google Sheets",
                "Review Pass 2 Results",
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
                create_or_update_profile(client_name)
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

        elif action == "Purge Classification Cache":
            try:
                db = ClientDB()
                client_id = db.get_client_id(client_name)

                # Ask for confirmation
                if questionary.confirm(
                    "Are you sure you want to purge the classification cache? This will force re-processing of all transactions, but won't delete existing classification results."
                ).ask():
                    with sqlite3.connect(db.db_path) as conn:
                        # Delete all cache entries for this client
                        conn.execute(
                            "DELETE FROM transaction_cache WHERE client_id = ?",
                            (client_id,),
                        )
                        click.echo(
                            "Cache purged successfully! You can now re-run classification to get fresh results."
                        )
                else:
                    click.echo("Cache purge cancelled.")

            except Exception as e:
                click.echo(f"Error purging cache: {e}")

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
                classifier = TransactionClassifier(client_name=client_name)

                # Determine processing parameters
                start_row = None
                end_row = None
                resume_from_pass = None

                if "Row Range" in action:
                    start_row = questionary.text(
                        "Start row (1-based):", default="1"
                    ).ask()
                    end_row = questionary.text(
                        f"End row (1-{len(transactions_df)}):",
                        default=str(len(transactions_df)),
                    ).ask()
                    try:
                        start_row = int(start_row)
                        end_row = int(end_row)
                        if (
                            start_row < 1
                            or end_row > len(transactions_df)
                            or start_row > end_row
                        ):
                            click.echo("Invalid row range")
                            continue
                    except ValueError:
                        click.echo("Invalid row numbers")
                        continue

                # Process transactions based on action
                if "Process All" in action:
                    # Process all passes
                    classifier.process_transactions(transactions_df, force_process=True)
                elif "Row Range" in action:
                    # Process each row in the range
                    for row_num in range(start_row, end_row + 1):
                        click.echo(f"\nProcessing row {row_num} of {end_row}...")
                        try:
                            classifier.process_single_row(
                                transactions_df, row_num, force_process=True
                            )
                        except Exception as e:
                            click.echo(f"Error processing row {row_num}: {str(e)}")
                            if not questionary.confirm("Continue with next row?").ask():
                                break
                    click.echo("\nRow range processing complete!")
                elif action.startswith("Pass "):
                    # Extract pass number and process specific pass
                    pass_num = int(action[5:6])  # "Pass 1", "Pass 2", "Pass 3"

                    # Check dependencies before running passes
                    if pass_num > 1:
                        # Check if Pass 1 has been completed
                        with sqlite3.connect(db.db_path) as conn:
                            cursor = conn.execute(
                                """
                                SELECT COUNT(*) 
                                FROM normalized_transactions t
                                LEFT JOIN transaction_classifications c 
                                    ON t.transaction_id = c.transaction_id 
                                    AND t.client_id = c.client_id
                                WHERE t.client_id = ? 
                                AND (c.payee IS NULL OR c.payee = '' OR c.payee = 'Unknown Payee')
                                """,
                                (db.get_client_id(client_name),),
                            )
                            missing_payees = cursor.fetchone()[0]

                            if missing_payees > 0:
                                # Instead of blocking, warn and ask for confirmation
                                click.echo(
                                    f"\nWarning: {missing_payees} transactions are missing valid payees."
                                )
                                click.echo(
                                    "These transactions will be skipped during Pass 2."
                                )
                                if not questionary.confirm(
                                    "Do you want to continue with Pass 2?"
                                ).ask():
                                    continue

                    if pass_num > 2:
                        # Check if Pass 2 has been completed
                        with sqlite3.connect(db.db_path) as conn:
                            cursor = conn.execute(
                                """
                                SELECT COUNT(*) 
                                FROM normalized_transactions t
                                LEFT JOIN transaction_classifications c 
                                    ON t.transaction_id = c.transaction_id 
                                    AND t.client_id = c.client_id
                                WHERE t.client_id = ? 
                                AND c.payee IS NOT NULL 
                                AND c.payee != 'Unknown Payee'
                                AND (c.category IS NULL OR c.category = '' OR c.category = 'Unclassified')
                                """,
                                (db.get_client_id(client_name),),
                            )
                            missing_categories = cursor.fetchone()[0]

                            if missing_categories > 0:
                                click.echo(
                                    f"Error: {missing_categories} transactions with valid payees are missing categories. Please run Pass 2 first."
                                )
                                continue

                    # For Pass 2, check for missing payees but don't block execution
                    if pass_num == 2:
                        with sqlite3.connect(db.db_path) as conn:
                            cursor = conn.execute(
                                """
                                SELECT COUNT(*) 
                                FROM normalized_transactions t
                                LEFT JOIN transaction_classifications c 
                                    ON t.transaction_id = c.transaction_id 
                                    AND t.client_id = c.client_id
                                WHERE t.client_id = ? 
                                AND (c.payee IS NULL OR c.payee = 'Unknown Payee')
                                """,
                                (db.get_client_id(client_name),),
                            )
                            missing_payees = cursor.fetchone()[0]

                            if missing_payees > 0:
                                click.echo(
                                    f"Warning: {missing_payees} transactions have missing or unknown payees and will be skipped during Pass 2."
                                )
                                if not questionary.confirm(
                                    "Do you want to continue?"
                                ).ask():
                                    continue

                    # For individual passes, we'll use resume_from_pass to control execution
                    # Pass 1: resume_from_pass=1 (only payee identification)
                    # Pass 2: resume_from_pass=2 (only category assignment)
                    # Pass 3: resume_from_pass=3 (only classification)
                    result_df = classifier.process_transactions(
                        transactions_df,
                        start_row=start_row,
                        end_row=end_row,
                        resume_from_pass=pass_num,
                    )

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

        elif action == "List Transactions":
            list_transactions(client_name)

        elif action == "View Transaction Status":
            try:
                # Get transactions from database
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)

                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                # Show transaction summary
                with sqlite3.connect(db.db_path) as conn:
                    # Define status colors
                    status_colors = {
                        "completed": "green",
                        "processing": "yellow",
                        "pending": "blue",
                        "error": "red",
                        "skipped": "magenta",
                        "force_required": "bright_red",
                    }

                    # Function to format status with color
                    def format_status(status, count):
                        color = status_colors.get(status, "white")
                        return click.style(
                            f"  {status}: {count} transactions", fg=color
                        )

                    # Pass 1 Status
                    cursor = conn.execute(
                        """
                        SELECT 
                            pass_1_status, COUNT(*) as count
                        FROM transaction_status
                        WHERE client_id = ?
                        GROUP BY pass_1_status
                        ORDER BY 
                            CASE pass_1_status
                                WHEN 'completed' THEN 1
                                WHEN 'processing' THEN 2
                                WHEN 'pending' THEN 3
                                WHEN 'error' THEN 4
                                WHEN 'skipped' THEN 5
                                WHEN 'force_required' THEN 6
                            END
                        """,
                        (db.get_client_id(client_name),),
                    )
                    click.echo("\nPass 1 (Payee Identification) Status:")
                    for status, count in cursor:
                        click.echo(format_status(status, count))

                    # Pass 2 Status
                    cursor = conn.execute(
                        """
                        SELECT 
                            pass_2_status, COUNT(*) as count
                        FROM transaction_status
                        WHERE client_id = ?
                        GROUP BY pass_2_status
                        ORDER BY 
                            CASE pass_2_status
                                WHEN 'completed' THEN 1
                                WHEN 'processing' THEN 2
                                WHEN 'pending' THEN 3
                                WHEN 'error' THEN 4
                                WHEN 'skipped' THEN 5
                                WHEN 'force_required' THEN 6
                            END
                        """,
                        (db.get_client_id(client_name),),
                    )
                    click.echo("\nPass 2 (Category Assignment) Status:")
                    for status, count in cursor:
                        click.echo(format_status(status, count))

                    # Pass 3 Status
                    cursor = conn.execute(
                        """
                        SELECT 
                            pass_3_status, COUNT(*) as count
                        FROM transaction_status
                        WHERE client_id = ?
                        GROUP BY pass_3_status
                        ORDER BY 
                            CASE pass_3_status
                                WHEN 'completed' THEN 1
                                WHEN 'processing' THEN 2
                                WHEN 'pending' THEN 3
                                WHEN 'error' THEN 4
                                WHEN 'skipped' THEN 5
                                WHEN 'force_required' THEN 6
                            END
                        """,
                        (db.get_client_id(client_name),),
                    )
                    click.echo("\nPass 3 (Classification) Status:")
                    for status, count in cursor:
                        click.echo(format_status(status, count))

                    # Show legend
                    click.echo("\nStatus Legend:")
                    for status, color in status_colors.items():
                        click.echo(click.style(f"  {status}", fg=color))

                # Allow viewing details of specific transactions
                while questionary.confirm("\nView specific transaction details?").ask():
                    transaction_id = questionary.text("Enter transaction ID:").ask()
                    status = db.get_transaction_status(client_name, transaction_id)
                    if status:
                        click.echo("\nTransaction Status:")
                        for pass_num, details in status.items():
                            click.echo(f"\n{pass_num.upper()}:")
                            status_color = status_colors.get(details["status"], "white")
                            click.echo(
                                click.style(
                                    f"  Status: {details['status']}", fg=status_color
                                )
                            )
                            if details["error"]:
                                click.echo(
                                    click.style(
                                        f"  Error: {details['error']}", fg="red"
                                    )
                                )
                            if details["processed_at"]:
                                click.echo(
                                    f"  Last Processed: {details['processed_at']}"
                                )
                    else:
                        click.echo("Transaction not found.")

            except Exception as e:
                click.echo(f"Error viewing transaction status: {e}")

        elif action == "Force Process Transactions":
            try:
                # Get transactions from database
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)

                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                # Show options for transaction selection
                selection_method = questionary.select(
                    "How would you like to select transactions?",
                    choices=[
                        "Enter Transaction IDs",
                        "Select by Status",
                        "Select by Date Range",
                        "Select All",
                    ],
                ).ask()

                transactions_to_process = []
                if selection_method == "Enter Transaction IDs":
                    # Allow entering multiple transaction IDs
                    while True:
                        transaction_id = questionary.text(
                            "Enter transaction ID (or leave empty to finish):"
                        ).ask()
                        if not transaction_id:
                            break
                        if transaction_id in transactions_df["transaction_id"].values:
                            transactions_to_process.append(transaction_id)
                        else:
                            click.echo("Transaction ID not found.")

                elif selection_method == "Select by Status":
                    status_choice = questionary.select(
                        "Select transactions with status:",
                        choices=["error", "pending", "force_required", "skipped"],
                    ).ask()

                    # Get transactions with selected status
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
                                status_choice,
                                status_choice,
                                status_choice,
                            ),
                        )
                        transactions_to_process = [row[0] for row in cursor.fetchall()]

                elif selection_method == "Select by Date Range":
                    start_date = questionary.text(
                        "Enter start date (YYYY-MM-DD):"
                    ).ask()
                    end_date = questionary.text("Enter end date (YYYY-MM-DD):").ask()

                    # Filter transactions by date range
                    mask = (transactions_df["transaction_date"] >= start_date) & (
                        transactions_df["transaction_date"] <= end_date
                    )
                    transactions_to_process = transactions_df[mask][
                        "transaction_id"
                    ].tolist()

                else:  # Select All
                    transactions_to_process = transactions_df["transaction_id"].tolist()

                if not transactions_to_process:
                    click.echo("No transactions selected.")
                    continue

                # Select pass to force
                pass_to_force = questionary.select(
                    "Which pass would you like to force?",
                    choices=[
                        "Pass 1: Payee Identification",
                        "Pass 2: Category Assignment",
                        "Pass 3: Classification",
                        "All Passes",
                    ],
                ).ask()

                # Get model type
                model_type = questionary.select(
                    "Select processing mode:",
                    choices=["fast", "precise"],
                ).ask()

                # Confirm processing
                if questionary.confirm(
                    f"Are you sure you want to process {len(transactions_to_process)} transactions?"
                ).ask():
                    # Initialize classifier
                    classifier = TransactionClassifier(
                        client_name=client_name,
                        db=db,
                        model_type=model_type,
                    )

                    # Process each transaction
                    for transaction_id in transactions_to_process:
                        click.echo(f"\nProcessing transaction {transaction_id}...")

                        # Process the transaction
                        if "Pass 1" in pass_to_force:
                            result_df = classifier.process_transactions(
                                transactions_df[
                                    transactions_df["transaction_id"] == transaction_id
                                ],
                                resume_from_pass=1,
                                force_process=True,
                            )
                        elif "Pass 2" in pass_to_force:
                            result_df = classifier.process_transactions(
                                transactions_df[
                                    transactions_df["transaction_id"] == transaction_id
                                ],
                                resume_from_pass=2,
                                force_process=True,
                            )
                        elif "Pass 3" in pass_to_force:
                            result_df = classifier.process_transactions(
                                transactions_df[
                                    transactions_df["transaction_id"] == transaction_id
                                ],
                                resume_from_pass=3,
                                force_process=True,
                            )
                        else:  # All Passes
                            result_df = classifier.process_transactions(
                                transactions_df[
                                    transactions_df["transaction_id"] == transaction_id
                                ],
                                force_process=True,
                            )

                    click.echo("\nSuccessfully processed all selected transactions")
                else:
                    click.echo("Processing cancelled")

            except Exception as e:
                click.echo(f"Error processing transactions: {e}")
                import traceback

                traceback.print_exc()

        elif action == "Reset Transaction Status":
            try:
                # Get transactions from database
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)

                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                # Get transaction ID
                transaction_id = questionary.text(
                    "Enter transaction ID to reset:"
                ).ask()

                # Get current status
                status = db.get_transaction_status(client_name, transaction_id)
                if not status:
                    click.echo("Transaction not found.")
                    continue

                # Show current status
                click.echo("\nCurrent Status:")
                for pass_num, details in status.items():
                    click.echo(f"{pass_num.upper()}: {details['status']}")

                # Select passes to reset
                passes_to_reset = questionary.checkbox(
                    "Select passes to reset:",
                    choices=[
                        "Pass 1: Payee Identification",
                        "Pass 2: Category Assignment",
                        "Pass 3: Classification",
                    ],
                ).ask()

                if not passes_to_reset:
                    click.echo("No passes selected.")
                    continue

                # Confirm reset
                if questionary.confirm(
                    "This will reset the selected passes to 'pending' status. Continue?"
                ).ask():
                    with sqlite3.connect(db.db_path) as conn:
                        updates = []
                        params = []
                        for pass_choice in passes_to_reset:
                            pass_num = pass_choice[5:6]  # Extract number from "Pass X:"
                            updates.append(f"pass_{pass_num}_status = ?")
                            updates.append(f"pass_{pass_num}_error = ?")
                            updates.append(f"pass_{pass_num}_processed_at = ?")
                            params.extend(["pending", None, None])

                        query = f"""
                        UPDATE transaction_status 
                        SET {", ".join(updates)},
                            updated_at = CURRENT_TIMESTAMP
                        WHERE client_id = ? AND transaction_id = ?
                        """
                        params.extend([db.get_client_id(client_name), transaction_id])

                        conn.execute(query, params)
                        click.echo("Successfully reset transaction status")
                else:
                    click.echo("Reset cancelled")

            except Exception as e:
                click.echo(f"Error resetting transaction status: {e}")

        elif action == "Reprocess Failed Transactions":
            try:
                # Get transactions from database
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)

                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                # Get transaction IDs of failed transactions
                failed_transactions = [
                    id
                    for id, status in db.get_transaction_status(client_name).items()
                    if status["status"] == "error"
                ]

                if not failed_transactions:
                    click.echo("No failed transactions found.")
                    continue

                # Confirm reprocessing
                if questionary.confirm(
                    f"Are you sure you want to reprocess {len(failed_transactions)} failed transactions? This will force re-processing of these transactions, but won't delete existing classification results."
                ).ask():
                    for transaction_id in failed_transactions:
                        # Process the transaction
                        result_df = classifier.process_transactions(
                            transactions_df[
                                transactions_df["transaction_id"] == transaction_id
                            ],
                            resume_from_pass=1,
                            force_process=True,
                        )
                    click.echo("Successfully reprocessed failed transactions")
                else:
                    click.echo("Reprocessing cancelled")

            except Exception as e:
                click.echo(f"Error reprocessing failed transactions: {e}")

        elif action == "Reprocess Pass for All Transactions":
            try:
                # Get transactions from database
                db = ClientDB()
                transactions_df = db.load_normalized_transactions(client_name)

                if transactions_df.empty:
                    click.echo("No transactions found.")
                    continue

                # Confirm reprocessing
                if questionary.confirm(
                    "Are you sure you want to reprocess all transactions? This will force re-processing of all transactions, but won't delete existing classification results."
                ).ask():
                    # Process all transactions
                    result_df = classifier.process_transactions(
                        transactions_df,
                        start_row=0,
                        end_row=len(transactions_df),
                    )
                    click.echo("Successfully reprocessed all transactions")
                else:
                    click.echo("Reprocessing cancelled")

            except Exception as e:
                click.echo(f"Error reprocessing all transactions: {e}")

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


if __name__ == "__main__":
    start_menu()
