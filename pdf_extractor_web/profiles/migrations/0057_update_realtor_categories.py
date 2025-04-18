from django.db import migrations


def update_categories(apps, schema_editor):
    BusinessProfile = apps.get_model("profiles", "BusinessProfile")
    IRSWorksheet = apps.get_model("profiles", "IRSWorksheet")
    IRSExpenseCategory = apps.get_model("profiles", "IRSExpenseCategory")
    BusinessExpenseCategory = apps.get_model("profiles", "BusinessExpenseCategory")

    # Get the business profile
    business = BusinessProfile.objects.get(client_id="Tim and Gene")

    # Delete existing categories
    BusinessExpenseCategory.objects.filter(business=business).delete()

    # Get the 6A worksheet
    worksheet_6a = IRSWorksheet.objects.get(name="6A")

    # Get parent categories
    other_expenses = IRSExpenseCategory.objects.get(
        worksheet=worksheet_6a, name="Other expenses"
    )
    office_expenses = IRSExpenseCategory.objects.get(
        worksheet=worksheet_6a, name="Office expense"
    )
    advertising = IRSExpenseCategory.objects.get(
        worksheet=worksheet_6a, name="Advertising"
    )

    # Define realtor-specific categories
    categories = [
        # Dues and Subscriptions
        (
            "Dues and Subscriptions",
            "Memberships (e.g., NAR), trade journals",
            other_expenses,
        ),
        (
            "MLS Dues",
            "Specific to real estate, access to the MLS database",
            other_expenses,
        ),
        # Open House and Staging
        (
            "Open House Expense",
            "Food, signs, printed materials for client events",
            advertising,
        ),
        (
            "Staging",
            "Furniture rental or decoration for showcasing properties",
            advertising,
        ),
        # Office Technology
        ("Computer & Internet", "Business use portion only", office_expenses),
    ]

    # Create categories
    for name, description, parent in categories:
        BusinessExpenseCategory.objects.get_or_create(
            business=business,
            category_name=name,
            defaults={
                "description": description,
                "worksheet": worksheet_6a,
                "parent_category": parent,
                "is_active": True,
                "tax_year": 2024,
            },
        )


def reverse_categories(apps, schema_editor):
    BusinessProfile = apps.get_model("profiles", "BusinessProfile")
    BusinessExpenseCategory = apps.get_model("profiles", "BusinessExpenseCategory")

    # Get the business profile
    business = BusinessProfile.objects.get(client_id="Tim and Gene")

    # Delete the new categories
    BusinessExpenseCategory.objects.filter(business=business).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0055_add_missing_transaction_fields"),
    ]

    operations = [
        migrations.RunPython(update_categories, reverse_categories),
    ]
