import click
import questionary
from typing import Dict, List, Optional
import os

from .client.client import ClientConfig
from .client.manager import ClientManager
from .parser.base import run_parser, check_for_pdf_files, create_test_pdf
from .sheets.client import upload_to_sheets


class CLI:
    """Command-line interface for PDF Extractor."""

    def __init__(self):
        self.client_manager = ClientManager()

    def start(self):
        """Start the CLI application."""
        while True:
            action = questionary.select(
                "What would you like to do?",
                choices=[
                    "Create a new client",
                    "Update an existing client",
                    "List all clients",
                    "Run parsers for a client",
                    "Upload results to Google Sheets",
                    "Delete a client",
                    "Exit",
                ],
            ).ask()

            if action == "Create a new client":
                self.create_client()
            elif action == "Update an existing client":
                self.update_client()
            elif action == "List all clients":
                self.list_clients()
            elif action == "Run parsers for a client":
                self.run_parsers()
            elif action == "Upload results to Google Sheets":
                self.upload_to_sheets()
            elif action == "Delete a client":
                self.delete_client()
            elif action == "Exit":
                break

    def create_client(self):
        """Create a new client."""
        client_name = questionary.text("Enter client name:").ask()

        if not client_name:
            click.echo("Client name cannot be empty.")
            return

        if self.client_manager.client_exists(client_name):
            click.echo(f"Client '{client_name}' already exists.")
            return

        config = self._run_client_questionnaire(client_name)

        if self.client_manager.create_client(config):
            click.echo(f"Client '{client_name}' created successfully.")
        else:
            click.echo(f"Failed to create client '{client_name}'.")

    def update_client(self):
        """Update an existing client."""
        clients = self.client_manager.list_clients()

        if not clients:
            click.echo("No clients found.")
            return

        client_name = questionary.select(
            "Select a client to update:", choices=clients
        ).ask()

        existing_config = self.client_manager.get_client(client_name)
        if not existing_config:
            click.echo(f"Failed to load client '{client_name}'.")
            return

        updated_config = self._run_client_questionnaire(client_name, existing_config)

        if self.client_manager.update_client(updated_config):
            click.echo(f"Client '{client_name}' updated successfully.")
        else:
            click.echo(f"Failed to update client '{client_name}'.")

    def list_clients(self):
        """List all clients with their details."""
        clients = self.client_manager.list_clients()

        if not clients:
            click.echo("No clients found.")
            return

        click.echo("\nClients:")
        for client_name in clients:
            config = self.client_manager.get_client(client_name)
            if config:
                click.echo(f"\n{config.client_name}")
                click.echo(f"  Business Type: {config.business_type or 'Not set'}")
                click.echo(f"  Industry: {config.industry or 'Not set'}")
                click.echo(f"  Location: {config.location or 'Not set'}")
                click.echo(f"  Annual Revenue: {config.annual_revenue or 'Not set'}")

                # Handle employee count properly
                emp_count = config.employee_count
                emp_display = str(emp_count) if emp_count is not None else "Not set"
                click.echo(f"  Employee Count: {emp_display}")

                # Handle lists properly
                activities = (
                    ", ".join(config.business_activities)
                    if config.business_activities
                    else "None"
                )
                click.echo(f"  Business Activities: {activities}")

                expenses = (
                    ", ".join(config.typical_expenses)
                    if config.typical_expenses
                    else "None"
                )
                click.echo(f"  Typical Expenses: {expenses}")

                click.echo(
                    f"  Last Updated: {config.last_updated.strftime('%Y-%m-%d %H:%M:%S')}"
                )

    def delete_client(self):
        """Delete a client."""
        clients = self.client_manager.list_clients()

        if not clients:
            click.echo("No clients found.")
            return

        client_name = questionary.select(
            "Select a client to delete:", choices=clients
        ).ask()

        confirm = questionary.confirm(
            f"Are you sure you want to delete client '{client_name}'? This cannot be undone."
        ).ask()

        if not confirm:
            click.echo("Operation cancelled.")
            return

        if self.client_manager.delete_client(client_name):
            click.echo(f"Client '{client_name}' deleted successfully.")
        else:
            click.echo(f"Failed to delete client '{client_name}'.")

    def run_parsers(self):
        """Run parsers for a client."""
        clients = self.client_manager.list_clients()

        if not clients:
            click.echo("No clients found.")
            return

        client_name = questionary.select(
            "Select a client to run parsers for:", choices=clients
        ).ask()

        # Check if client has any PDF files
        has_pdf_files = check_for_pdf_files(client_name)

        # Show instructions for PDF placement
        click.echo("\n" + "-" * 60)
        click.echo("PDF PROCESSING INSTRUCTIONS")
        click.echo("-" * 60)
        click.echo(
            "To process PDF files, place them in the appropriate input directories:"
        )
        click.echo(f"data/clients/{client_name}/input/<parser_type>/")
        click.echo("\nAvailable parser types:")
        click.echo("  • amazon - For Amazon order invoices")
        click.echo("  • bofa_bank - For Bank of America bank statements")
        click.echo("  • bofa_visa - For Bank of America credit card statements")
        click.echo("  • chase_visa - For Chase Visa credit card statements")
        click.echo("  • wellsfargo_bank - For Wells Fargo bank statements")
        click.echo("  • wellsfargo_mastercard - For Wells Fargo Mastercard statements")
        click.echo("  • wellsfargo_visa - For Wells Fargo Visa statements")
        click.echo("  • wellsfargo_bank_csv - For Wells Fargo bank CSV exports")
        click.echo("  • first_republic_bank - For First Republic bank statements")
        click.echo("-" * 60)

        if not has_pdf_files:
            click.echo("\n⚠️ No PDF files found for this client.")
            click.echo(
                "Please add PDF files to the appropriate input directories before running parsers."
            )

            # Ask if they want to create a test file
            create_test = questionary.confirm(
                "Would you like to create a test PDF file for demonstration purposes?"
            ).ask()

            if create_test:
                parser_type = questionary.select(
                    "Which parser type would you like to create a test file for?",
                    choices=[
                        "amazon",
                        "bofa_bank",
                        "bofa_visa",
                        "chase_visa",
                        "wellsfargo_bank",
                        "wellsfargo_mastercard",
                        "wellsfargo_visa",
                        "wellsfargo_bank_csv",
                        "first_republic_bank",
                    ],
                ).ask()

                if create_test_pdf(client_name, parser_type):
                    click.echo(
                        f"\n✓ Test PDF file created in data/clients/{client_name}/input/{parser_type}/"
                    )
                    has_pdf_files = True
                else:
                    click.echo("\n⚠️ Failed to create test PDF file.")

                    # Ask if they want to continue anyway
                    continue_anyway = questionary.confirm(
                        "Do you want to continue anyway?"
                    ).ask()

                    if not continue_anyway:
                        return
            else:
                # Ask if they want to continue anyway
                continue_anyway = questionary.confirm(
                    "Do you want to continue anyway?"
                ).ask()

                if not continue_anyway:
                    return
        else:
            click.echo("\n✓ PDF files found and ready to process.")

        # Confirm before running
        confirm = questionary.confirm(
            f"Do you want to run parsers for client '{client_name}'? This will process all PDF files."
        ).ask()

        if not confirm:
            click.echo("Operation cancelled.")
            return

        # Run parsers using the existing system
        success = run_parser(client_name)

        if success:
            click.echo("\nParser execution completed successfully.")

            # Ask if user wants to see the output files
            show_output = questionary.confirm(
                "Would you like to see a list of the output files?"
            ).ask()

            if show_output:
                output_dir = os.path.join("data", "clients", client_name, "output")
                if os.path.exists(output_dir):
                    output_files = os.listdir(output_dir)
                    if output_files:
                        click.echo("\nOutput files:")
                        for file in output_files:
                            click.echo(f"  • {file}")
                    else:
                        click.echo("\nNo output files found.")
                else:
                    click.echo(f"\nOutput directory not found: {output_dir}")
        else:
            click.echo("\nParser execution completed with no results.")
            click.echo(
                "Check that you have placed PDF files in the correct input directories."
            )

    def upload_to_sheets(self):
        """Upload results to Google Sheets."""
        clients = self.client_manager.list_clients()

        if not clients:
            click.echo("No clients found.")
            return

        client_name = questionary.select(
            "Select a client to upload results for:", choices=clients
        ).ask()

        # Here you would handle Google Sheets upload
        # Simplified for this example
        click.echo(f"Uploading results for client '{client_name}' to Google Sheets...")

        # This would call your actual Sheets API implementation
        success = upload_to_sheets(client_name)

        if success:
            click.echo("Results uploaded successfully.")
        else:
            click.echo("Failed to upload results.")

    def _run_client_questionnaire(
        self, client_name: str, existing_config: Optional[ClientConfig] = None
    ) -> ClientConfig:
        """Run interactive questionnaire for client information."""
        # Start with existing config or create new one
        config = existing_config or ClientConfig(client_name=client_name)

        # Show current value in prompt if updating
        current = lambda field, default="": (
            f" (current: {field})" if field else f" (current: {default})"
        )

        # Business type
        business_type = questionary.text(
            f"Business type{current(config.business_type, 'Not set')}:",
            default=config.business_type or "",
        ).ask()

        # Industry
        industry = questionary.text(
            f"Industry{current(config.industry, 'Not set')}:",
            default=config.industry or "",
        ).ask()

        # Location
        location = questionary.text(
            f"Location{current(config.location, 'Not set')}:",
            default=config.location or "",
        ).ask()

        # Annual revenue
        annual_revenue = questionary.text(
            f"Annual revenue{current(config.annual_revenue, 'Not set')}:",
            default=config.annual_revenue or "",
        ).ask()

        # Employee count
        employee_count_str = questionary.text(
            f"Employee count{current(config.employee_count, 'Not set')}:",
            default=(
                str(config.employee_count) if config.employee_count is not None else ""
            ),
        ).ask()

        # Parse employee count
        try:
            employee_count = int(employee_count_str) if employee_count_str else None
        except ValueError:
            employee_count = None

        # Business activities
        activities_str = questionary.text(
            f"Business activities (comma-separated){current(', '.join(config.business_activities), 'None')}:",
            default=", ".join(config.business_activities),
        ).ask()

        # Parse activities
        activities = (
            [item.strip() for item in activities_str.split(",") if item.strip()]
            if activities_str
            else []
        )

        # Typical expenses
        expenses_str = questionary.text(
            f"Typical expenses (comma-separated){current(', '.join(config.typical_expenses), 'None')}:",
            default=", ".join(config.typical_expenses),
        ).ask()

        # Parse expenses
        expenses = (
            [item.strip() for item in expenses_str.split(",") if item.strip()]
            if expenses_str
            else []
        )

        # Update config
        config.business_type = business_type or None
        config.industry = industry or None
        config.location = location or None
        config.annual_revenue = annual_revenue or None
        config.employee_count = employee_count
        config.business_activities = activities
        config.typical_expenses = expenses

        return config
