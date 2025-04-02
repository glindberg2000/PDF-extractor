"""Command-line menu interface for DataExtractAI."""

import typer
from typing import Optional
import os
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from ..utils.config import (
    CATEGORIES,
    CLASSIFICATIONS,
    PARSER_OUTPUT_PATHS,
    update_config_for_client,
    get_client_sheets_config,
)
from ..sheets.excel_formatter import ExcelReportFormatter
import pandas as pd

console = Console()
app = typer.Typer()


def display_main_menu():
    """Display the main menu options."""
    menu = Table(show_header=False, box=box.ROUNDED)
    menu.add_column("Option", style="cyan")
    menu.add_column("Description")

    menu.add_row("1", "Process Documents")
    menu.add_row("2", "Categorize Transactions")
    menu.add_row("3", "Data Export")
    menu.add_row("4", "Client Management")
    menu.add_row("5", "Exit")

    console.print(Panel(menu, title="Main Menu", subtitle="Select an option"))


def display_export_menu():
    """Display the data export menu options."""
    menu = Table(show_header=False, box=box.ROUNDED)
    menu.add_column("Option", style="cyan")
    menu.add_column("Description")

    menu.add_row("1", "Export to Excel (with validation & charts)")
    menu.add_row("2", "Upload to Google Sheets")
    menu.add_row("3", "Back to Main Menu")

    console.print(Panel(menu, title="Data Export Menu", subtitle="Select an option"))


def export_to_excel(client: Optional[str] = None):
    """Export data to Excel with validation and charts."""
    try:
        # Get the input CSV file path
        csv_file = PARSER_OUTPUT_PATHS["consolidated_batched"]["csv"]
        if not os.path.exists(csv_file):
            console.print(
                "[red]No processed data found. Please process transactions first.[/red]"
            )
            return

        # Read the CSV data
        df = pd.read_csv(csv_file)

        # Create the output directory if it doesn't exist
        output_dir = os.path.join("data", "output", "excel")
        os.makedirs(output_dir, exist_ok=True)

        # Generate output filename
        client_prefix = f"{client}_" if client else ""
        output_file = os.path.join(output_dir, f"{client_prefix}transactions.xlsx")

        # Create the Excel report
        console.print(
            "[green]Creating Excel report with validation and charts...[/green]"
        )
        formatter = ExcelReportFormatter()
        formatter.create_report(
            data=df,
            output_path=output_file,
            categories=CATEGORIES,
            classifications=CLASSIFICATIONS,
        )

        console.print(
            f"[green]Excel file created successfully at: {output_file}[/green]"
        )

    except Exception as e:
        console.print(f"[red]Error creating Excel file: {str(e)}[/red]")


def handle_export_menu():
    """Handle the data export menu options."""
    while True:
        display_export_menu()
        choice = typer.prompt("Enter your choice")

        if choice == "1":
            client = typer.prompt("Enter client name (optional)", default="")
            export_to_excel(client if client else None)
        elif choice == "2":
            console.print("[yellow]Google Sheets upload temporarily disabled.[/yellow]")
        elif choice == "3":
            break
        else:
            console.print("[red]Invalid choice. Please try again.[/red]")


def main():
    """Main menu loop."""
    while True:
        display_main_menu()
        choice = typer.prompt("Enter your choice")

        if choice == "1":
            console.print("Process Documents selected")
            # TODO: Implement document processing menu
        elif choice == "2":
            console.print("Categorize Transactions selected")
            # TODO: Implement transaction categorization menu
        elif choice == "3":
            handle_export_menu()
        elif choice == "4":
            console.print("Client Management selected")
            # TODO: Implement client management menu
        elif choice == "5":
            console.print("[green]Goodbye![/green]")
            break
        else:
            console.print("[red]Invalid choice. Please try again.[/red]")


if __name__ == "__main__":
    typer.run(main)
