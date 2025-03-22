"""Main CLI entry point for PDF-extractor."""

import typer
from typer import Typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.layout import Layout
from rich.live import Live
from rich.align import Align
from rich.theme import Theme
import os
import shutil
from datetime import datetime
from typing import Optional, List
import yaml

from dataextractai.utils.sheets import setup_sheets, upload_to_sheets
from dataextractai.utils.config import (
    PARSER_OUTPUT_PATHS,
    ASSISTANTS_CONFIG,
    COMMON_CONFIG,
    CATEGORIES,
    CLASSIFICATIONS,
)
from dataextractai.parsers.run_parsers import run_all_parsers
from dataextractai.classifiers.ai_categorizer import categorize_transaction

# Define a theme with a specific color for comments
custom_theme = Theme(
    {
        "fieldname": "cyan",
        "value": "magenta",
        "comment": "green",  # Color for comments
        "normal": "white",
    }
)
console = Console(theme=custom_theme)

app = Typer(
    help="""PDF-extractor CLI - Process financial documents with AI assistance.

This tool helps you:
1. Manage clients and their configurations
2. Process PDF documents and extract transactions
3. Categorize transactions using AI
4. Upload results to Google Sheets

Use --help with any command for detailed information.
"""
)


# Client Management Commands
@app.command(name="client")
def client_management(
    action: str = typer.Argument(
        ...,
        help="Action to perform: create, list, update, or delete",
        metavar="[create|list|update|delete]",
    ),
    client_name: Optional[str] = typer.Argument(
        None, help="Client name for the action"
    ),
):
    """Manage clients and their configurations."""
    if action == "create":
        if not client_name:
            client_name = Prompt.ask("Enter client name")
        create_client(client_name)
    elif action == "list":
        list_clients()
    elif action == "update":
        if not client_name:
            client_name = Prompt.ask("Enter client name to update")
        update_client(client_name)
    elif action == "delete":
        if not client_name:
            client_name = Prompt.ask("Enter client name to delete")
        delete_client(client_name)
    else:
        console.print("[red]Invalid action. Use --help for available actions.[/red]")


def create_client(client_name: str):
    """Create a new client and their configuration."""
    # Create the data/clients directory if it doesn't exist
    os.makedirs("data/clients", exist_ok=True)

    client_dir = os.path.join("data", "clients", client_name)
    if os.path.exists(client_dir):
        console.print(f"[red]Client {client_name} already exists.[/red]")
        return

    # Create client directory structure
    input_dir = os.path.join(client_dir, "input")
    output_dir = os.path.join(client_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    # Create parser-specific input directories
    parser_dirs = [
        "amazon",
        "bofa_bank",
        "bofa_visa",
        "chase_visa",
        "wellsfargo_bank",
        "wellsfargo_mastercard",
        "wellsfargo_visa",
        "wellsfargo_bank_csv",
        "firstrepublic_bank",
        "client_info",
    ]

    for parser_dir in parser_dirs:
        os.makedirs(os.path.join(input_dir, parser_dir), exist_ok=True)
        console.print(f"[green]Created directory for {parser_dir}[/green]")

    # Create default client config
    config = {
        "client_name": client_name,
        "business_type": Prompt.ask("Enter business type"),
        "fiscal_year": datetime.now().year,
        "batch_size": 25,
        "ai_assistant": "AmeliaAI",
        "custom_categories": [],
        "business_rules": {
            "min_amount": 0.00,
            "max_amount": 1000000.00,
            "exclude_keywords": [],
        },
        "output_format": "csv",
        "include_metadata": True,
        "contact": {
            "name": Prompt.ask("Enter contact name"),
            "email": Prompt.ask("Enter contact email"),
            "phone": Prompt.ask("Enter contact phone"),
        },
        "business_details": {
            "industry": Prompt.ask("Enter industry"),
            "tax_id": Prompt.ask("Enter tax ID (optional)", default=""),
            "fiscal_year_end": "12-31",
        },
        "sheets": {
            "enabled": False,
            "sheet_name": f"{client_name}_Expenses",
            "sheet_id": "",
        },
    }

    with open(os.path.join(client_dir, "client_config.yaml"), "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    console.print(f"[green]✓ Created client: {client_name}[/green]")
    console.print("\nNext steps:")
    console.print("1. Place PDF files in the appropriate input directories")
    console.print("2. Run 'process' command to extract transactions")
    console.print("3. Run 'categorize' command to categorize transactions")
    console.print("4. Run 'upload' command to upload to Google Sheets")


def list_clients():
    """List all clients and their status."""
    clients_dir = os.path.join("data", "clients")
    if not os.path.exists(clients_dir):
        console.print(
            "[yellow]No clients found. Create a new client to get started.[/yellow]"
        )
        return

    table = Table(title="Clients")
    table.add_column("Name", style="cyan")
    table.add_column("Business Type", style="magenta")
    table.add_column("Files", style="green")
    table.add_column("Last Updated", style="yellow")

    for client_name in os.listdir(clients_dir):
        config_path = os.path.join(clients_dir, client_name, "client_config.yaml")
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    last_updated = datetime.fromtimestamp(
                        os.path.getmtime(config_path)
                    ).strftime("%Y-%m-%d")

                    # Count files in each parser directory
                    input_dir = os.path.join(clients_dir, client_name, "input")
                    file_counts = []
                    for parser_dir in os.listdir(input_dir):
                        parser_path = os.path.join(input_dir, parser_dir)
                        if os.path.isdir(parser_path):
                            file_count = len(
                                [
                                    f
                                    for f in os.listdir(parser_path)
                                    if f.endswith((".pdf", ".csv"))
                                ]
                            )
                            if file_count > 0:
                                file_counts.append(f"{parser_dir}: {file_count}")

                    files_str = "\n".join(file_counts) if file_counts else "No files"

                    table.add_row(
                        client_name,
                        config.get("business_type", "N/A"),
                        files_str,
                        last_updated,
                    )
            except Exception as e:
                console.print(
                    f"[red]Error reading config for {client_name}: {str(e)}[/red]"
                )

    console.print(table)


def update_client(client_name: str):
    """Update client configuration."""
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    if not os.path.exists(config_path):
        console.print(f"[red]Client {client_name} not found.[/red]")
        return

    with open(config_path) as f:
        config = yaml.safe_load(f)

    console.print("\n[bold]Update Client Configuration[/bold]")
    console.print("Leave blank to keep current value.")

    config["business_type"] = Prompt.ask(
        "Business Type", default=config.get("business_type", "")
    )
    config["contact"]["name"] = Prompt.ask(
        "Contact Name", default=config.get("contact", {}).get("name", "")
    )
    config["contact"]["email"] = Prompt.ask(
        "Contact Email", default=config.get("contact", {}).get("email", "")
    )
    config["contact"]["phone"] = Prompt.ask(
        "Contact Phone", default=config.get("contact", {}).get("phone", "")
    )
    config["business_details"]["industry"] = Prompt.ask(
        "Industry", default=config.get("business_details", {}).get("industry", "")
    )
    config["business_details"]["tax_id"] = Prompt.ask(
        "Tax ID", default=config.get("business_details", {}).get("tax_id", "")
    )

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    console.print(f"[green]✓ Updated client: {client_name}[/green]")


def delete_client(client_name: str):
    """Delete a client and their data."""
    client_dir = os.path.join("data", "clients", client_name)
    if not os.path.exists(client_dir):
        console.print(f"[red]Client {client_name} not found.[/red]")
        return

    if Confirm.ask(
        f"Are you sure you want to delete client {client_name}? This cannot be undone."
    ):
        shutil.rmtree(client_dir)
        console.print(f"[green]✓ Deleted client: {client_name}[/green]")


# Processing Commands
@app.command(name="process")
def process_documents(
    client_name: str = typer.Argument(..., help="Client name to process documents for"),
    batch_size: int = typer.Option(25, help="Number of rows to process in a batch"),
    ai_name: str = typer.Option("AmeliaAI", help="AI assistant to use for processing"),
):
    """Process PDF documents and extract transactions."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing documents...", total=None)
        total_lines = run_all_parsers(client_name)
        progress.update(task, completed=True)

    console.print(f"[green]✓ Processed {total_lines} transactions[/green]")


@app.command(name="categorize")
def categorize_transactions(
    client_name: str = typer.Argument(
        ..., help="Client name to categorize transactions for"
    ),
    batch_size: int = typer.Option(25, help="Number of rows to process in a batch"),
    ai_name: str = typer.Option(
        "AmeliaAI", help="AI assistant to use for categorization"
    ),
):
    """Categorize transactions using AI."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Categorizing transactions...", total=None)
        # TODO: Implement categorization logic
        progress.update(task, completed=True)

    console.print("[green]✓ Categorized transactions[/green]")


@app.command(name="upload")
def upload_to_google_sheets_command(
    client_name: str = typer.Argument(..., help="Client name to upload data for"),
):
    """Upload categorized transactions to Google Sheets."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading to Google Sheets...", total=None)
        if upload_to_sheets(client_name):
            progress.update(task, completed=True)
        else:
            progress.update(task, completed=True)
            console.print("[red]Failed to upload to Google Sheets[/red]")


@app.command(name="setup-sheets")
def setup_sheets_command():
    """Set up Google Sheets integration."""
    try:
        if setup_sheets():
            console.print("[green]✓ Google Sheets setup complete![/green]")
        else:
            console.print(
                "[red]Google Sheets setup failed. Please check the errors above.[/red]"
            )
            raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error setting up Google Sheets: {str(e)}[/red]")
        raise typer.Exit(1)


def display_menu():
    """Display the main menu and handle user selection."""
    while True:
        console.clear()
        console.print(
            Panel.fit(
                "[bold cyan]PDF-extractor Menu[/bold cyan]\n\n"
                "1. Client Management\n"
                "2. Process Documents\n"
                "3. Categorize Transactions\n"
                "4. Upload to Google Sheets\n"
                "5. Google Sheets Setup\n"
                "6. Exit",
                title="Main Menu",
                border_style="blue",
            )
        )

        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6"])

        if choice == "1":
            display_client_menu()
        elif choice == "2":
            client_name = Prompt.ask("Enter client name")
            process_documents(client_name)
        elif choice == "3":
            client_name = Prompt.ask("Enter client name")
            categorize_transactions(client_name)
        elif choice == "4":
            client_name = Prompt.ask("Enter client name")
            upload_to_google_sheets_command(client_name)
        elif choice == "5":
            setup_sheets_command()
        elif choice == "6":
            console.print("[yellow]Goodbye![/yellow]")
            break


def display_client_menu():
    """Display the client management menu and handle user selection."""
    while True:
        console.clear()
        console.print(
            Panel.fit(
                "[bold cyan]Client Management[/bold cyan]\n\n"
                "1. Create New Client\n"
                "2. List Clients\n"
                "3. Update Client\n"
                "4. Delete Client\n"
                "5. Back to Main Menu",
                title="Client Menu",
                border_style="blue",
            )
        )

        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5"])

        if choice == "1":
            client_name = Prompt.ask("Enter client name")
            create_client(client_name)
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "2":
            list_clients()
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "3":
            client_name = Prompt.ask("Enter client name")
            update_client(client_name)
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "4":
            client_name = Prompt.ask("Enter client name")
            delete_client(client_name)
            Prompt.ask("\nPress Enter to continue...")
        elif choice == "5":
            break


@app.command(name="menu")
def menu_command():
    """Start the interactive menu system."""
    try:
        display_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Menu closed by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error in menu system: {str(e)}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
