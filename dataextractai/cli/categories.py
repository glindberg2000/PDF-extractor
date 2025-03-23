"""Category management commands for the CLI."""

import os
import yaml
from typing import List, Dict, Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel

from dataextractai.utils.ai import (
    generate_categories,
    CATEGORIES,
    generate_category_details,
)
from dataextractai.utils.config import get_client_config

console = Console()


def list_categories(client_name: str):
    """List all categories for a client."""
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    if not os.path.exists(config_path):
        console.print("[red]Error: Could not find client configuration[/red]")
        return

    # Load config directly from file
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    table = Table(title=f"Categories for {client_name}")
    table.add_column("#", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Tax Implications", style="yellow")
    table.add_column("Source", style="blue")

    # Get custom categories first
    custom_categories = config.get("custom_categories", [])
    custom_names = {cat.get("name", "").lower() for cat in custom_categories}

    # List system categories that don't overlap with custom categories
    for i, category in enumerate(CATEGORIES, 1):
        # Skip if there's a custom category with a similar name
        if category.lower() in custom_names:
            continue

        table.add_row(
            str(i),
            category,
            "System default category",
            "EXPENSE",
            "",
            "System",
        )

    # List custom categories
    for i, category in enumerate(custom_categories, len(table.rows) + 1):
        table.add_row(
            str(i),
            category.get("name", ""),
            category.get("description", ""),
            category.get("type", "EXPENSE"),
            category.get("tax_implications", ""),
            "Custom",
        )

    console.print(table)


def add_category(client_name: str):
    """Add a new category for a client using AI assistance."""
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    if not os.path.exists(config_path):
        console.print("[red]Error: Could not find client configuration[/red]")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    console.print("\n[bold]Add New Category[/bold]")
    console.print(
        "Describe the category you want to add. The AI will help format it correctly."
    )
    description = Prompt.ask("Category description")

    # Use AI to generate proper category name and details
    category_details = generate_category_details(description, client_name)

    if not category_details:
        console.print(
            "[red]Failed to generate category details. Please try again.[/red]"
        )
        return

    # Check if similar system category exists
    if category_details.get("system_category_match") == "true":
        console.print(
            f"\n[bold]System category match found: {category_details['matching_system_category']}[/bold]"
        )
        if Confirm.ask("Would you like to use the system category name instead?"):
            category_details["name"] = category_details["matching_system_category"]

    # Check if category already exists
    custom_categories = config.get("custom_categories", [])
    if any(
        cat.get("name", "").lower() == category_details["name"].lower()
        for cat in custom_categories
    ):
        console.print(
            f"[red]Category '{category_details['name']}' already exists.[/red]"
        )
        return

    new_category = {
        "name": category_details["name"],
        "description": category_details["description"],
        "type": category_details["type"],
        "tax_implications": category_details["tax_implications"],
        "is_system_default": category_details.get("system_category_match") == "true",
        "is_auto_generated": False,
        "confidence": category_details.get("confidence", "MEDIUM"),
    }

    if not "custom_categories" in config:
        config["custom_categories"] = []

    config["custom_categories"].append(new_category)

    # Save updated config
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    console.print(f"[green]✓ Added category: {new_category['name']}[/green]")
    console.print("\nCategory details:")
    console.print(f"Description: {new_category['description']}")
    console.print(f"Type: {new_category['type']}")
    console.print(f"Tax Implications: {new_category['tax_implications']}")
    console.print(f"Confidence: {new_category['confidence']}")

    # Display updated categories
    list_categories(client_name)


def edit_category(client_name: str):
    """Edit an existing category using AI assistance."""
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    if not os.path.exists(config_path):
        console.print("[red]Error: Could not find client configuration[/red]")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    custom_categories = config.get("custom_categories", [])
    if not custom_categories:
        console.print("[yellow]No custom categories to edit[/yellow]")
        return

    console.print("\n[bold]Edit Category[/bold]")
    console.print(
        "Describe which category you want to edit and how you want to modify it."
    )
    console.print(
        "Example: 'Change the description of the Travel Expenses category to include more details about mileage tracking'"
    )
    description = Prompt.ask("Category description and changes")

    # Use AI to identify and update the category
    from dataextractai.utils.ai import generate_category_details

    updated_details = generate_category_details(description, client_name)

    if not updated_details:
        console.print(
            "[red]Failed to generate updated category details. Please try again.[/red]"
        )
        return

    # Find matching category
    matching_categories = [
        cat
        for cat in custom_categories
        if cat.get("name", "").lower() == updated_details["name"].lower()
    ]

    if not matching_categories:
        console.print(
            f"[red]No category found matching '{updated_details['name']}'[/red]"
        )
        return

    category = matching_categories[0]
    console.print(f"\n[bold]Found category: {category['name']}[/bold]")
    console.print("\nCurrent details:")
    console.print(f"Description: {category.get('description', '')}")
    console.print(f"Type: {category.get('type', 'EXPENSE')}")
    console.print(f"Tax Implications: {category.get('tax_implications', '')}")

    console.print("\nProposed changes:")
    console.print(f"Description: {updated_details['description']}")
    console.print(f"Type: {updated_details['type']}")
    console.print(f"Tax Implications: {updated_details['tax_implications']}")

    if Confirm.ask("Apply these changes?"):
        # Check if similar system category exists
        if updated_details.get("system_category_match") == "true":
            console.print(
                f"\n[bold]System category match found: {updated_details['matching_system_category']}[/bold]"
            )
            if Confirm.ask("Would you like to use the system category name instead?"):
                updated_details["name"] = updated_details["matching_system_category"]

        # Update category
        category.update(
            {
                "name": updated_details["name"],
                "description": updated_details["description"],
                "type": updated_details["type"],
                "tax_implications": updated_details["tax_implications"],
                "is_system_default": updated_details.get("system_category_match")
                == "true",
                "confidence": updated_details.get("confidence", "MEDIUM"),
            }
        )

        # Save updated config
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        console.print(f"[green]✓ Updated category: {category['name']}[/green]")
        list_categories(client_name)


def delete_category(client_name: str):
    """Delete a category for a client."""
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    if not os.path.exists(config_path):
        console.print("[red]Error: Could not find client configuration[/red]")
        return

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    custom_categories = config.get("custom_categories", [])
    if not custom_categories:
        console.print("[yellow]No custom categories to delete[/yellow]")
        return

    console.print("\n[bold]Delete Category[/bold]")
    console.print("Enter either the category number or exact name to delete.")
    console.print("\nCurrent custom categories:")
    for i, cat in enumerate(custom_categories, 1):
        console.print(f"{i}. {cat.get('name', '')}")

    selection = Prompt.ask("Category number or name").strip()

    # Try to parse as number first
    try:
        index = int(selection) - 1
        if 0 <= index < len(custom_categories):
            category = custom_categories[index]
        else:
            console.print("[red]Invalid category number[/red]")
            return
    except ValueError:
        # If not a number, try to match by name
        matching_categories = [
            cat
            for cat in custom_categories
            if cat.get("name", "").lower() == selection.lower()
        ]
        if not matching_categories:
            console.print(f"[red]No category found with name '{selection}'[/red]")
            return
        category = matching_categories[0]

    console.print(f"\n[bold]Found category: {category['name']}[/bold]")
    console.print(f"Description: {category.get('description', '')}")
    console.print(f"Type: {category.get('type', 'EXPENSE')}")
    console.print(f"Tax Implications: {category.get('tax_implications', '')}")

    if Confirm.ask(f"Are you sure you want to delete this category?"):
        custom_categories.remove(category)
        config["custom_categories"] = custom_categories

        # Save updated config
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        console.print(f"[green]✓ Deleted category: {category['name']}[/green]")
        list_categories(client_name)


def generate_categories_for_client(client_name: str):
    """Generate AI-suggested categories for a client."""
    config_path = os.path.join("data", "clients", client_name, "client_config.yaml")
    if not os.path.exists(config_path):
        console.print("[red]Error: Could not find client configuration[/red]")
        return

    # Load config directly from file
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Check for required business information
    business_type = config.get("business_type", "")
    business_details = config.get("business_details", {})
    industry = business_details.get("industry", "")
    business_activities = business_details.get("business_activities", [])
    typical_expenses = business_details.get("typical_expenses", [])
    location = business_details.get("location", "")
    annual_revenue = business_details.get("annual_revenue", "")

    # Build a comprehensive business description
    business_description = (
        f"This is a {business_type} business in the {industry} industry. "
    )
    if business_activities:
        business_description += (
            f"Their main activities include: {', '.join(business_activities)}. "
        )
    if location:
        business_description += f"Located in {location}. "
    if annual_revenue:
        business_description += f"Annual revenue: {annual_revenue}. "
    if typical_expenses:
        business_description += (
            f"Typical expenses include: {', '.join(typical_expenses)}."
        )

    if not business_type or not industry:
        console.print(
            "[red]Missing business type or industry. Please update client profile first.[/red]"
        )
        console.print("Current values:")
        console.print(f"Business Type: {business_type or '[red]Missing[/red]'}")
        console.print(f"Industry: {industry or '[red]Missing[/red]'}")
        return

    console.print("\n[bold]Generating Categories[/bold]")
    console.print("This may take a few moments...")

    # Generate categories using AI
    categories = generate_categories(
        business_type=business_type,
        industry=industry,
        business_description=business_description,
        typical_expenses=typical_expenses,
        business_activities=business_activities,
    )

    if not categories:
        console.print("[red]Failed to generate categories. Please try again.[/red]")
        return

    # Display generated categories
    table = Table(title="Generated Categories")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="magenta")
    table.add_column("Type", style="green")
    table.add_column("Tax Implications", style="yellow")

    for category in categories:
        table.add_row(
            category.get("name", ""),
            category.get("description", ""),
            category.get("type", "EXPENSE"),
            category.get("tax_implications", ""),
        )

    console.print(table)

    # Ask if user wants to add these categories
    if Confirm.ask(
        "\nWould you like to add these categories to the client configuration?"
    ):
        if "custom_categories" not in config:
            config["custom_categories"] = []

        custom_categories = config["custom_categories"]
        # Remove any duplicates based on category name
        existing_names = {cat.get("name", "") for cat in custom_categories}
        new_categories = [
            cat for cat in categories if cat.get("name", "") not in existing_names
        ]
        custom_categories.extend(new_categories)
        config["custom_categories"] = custom_categories

        # Save updated config
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        console.print(
            f"[green]✓ Added {len(new_categories)} new categories to client configuration[/green]"
        )
