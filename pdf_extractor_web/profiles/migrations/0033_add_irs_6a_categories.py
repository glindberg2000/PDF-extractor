from django.db import migrations


def add_6a_categories(apps, schema_editor):
    IRSWorksheet = apps.get_model("profiles", "IRSWorksheet")
    IRSExpenseCategory = apps.get_model("profiles", "IRSExpenseCategory")

    # Create the 6A worksheet
    worksheet_6a, _ = IRSWorksheet.objects.get_or_create(
        name="6A",
        defaults={
            "description": "Schedule C (Form 1040) Profit or Loss from Business - Part II Expenses",
            "is_active": True,
        },
    )

    # Standard 6A expense categories with their line numbers
    categories = [
        ("Advertising", "8", "Business advertising and promotional expenses"),
        (
            "Car and truck expenses",
            "9",
            "Vehicle expenses using actual or standard mileage rate",
        ),
        (
            "Parking fees and tolls",
            "9",
            "Parking fees and tolls related to business use",
        ),
        (
            "Commissions and fees",
            "10",
            "Commissions and fees paid for business services",
        ),
        ("Contract labor", "11", "Payments to independent contractors"),
        (
            "Employee benefit programs and health insurance",
            "14",
            "Employee benefits excluding pension/profit-sharing",
        ),
        (
            "Insurance (other than health)",
            "15",
            "Business insurance excluding health insurance",
        ),
        ("Interest - mortgage", "16a", "Mortgage interest paid to banks"),
        ("Interest - other", "16b", "Other business-related interest payments"),
        (
            "Legal and professional fees",
            "17",
            "Legal, accounting, and professional services",
        ),
        ("Office expense", "18", "General office expenses and supplies"),
        (
            "Pension and profit-sharing plans",
            "19",
            "Contributions to employee pension/profit-sharing",
        ),
        (
            "Rent/lease - vehicles, machinery, equipment",
            "20a",
            "Rental/lease payments for business equipment",
        ),
        (
            "Rent/lease - other business property",
            "20b",
            "Rental/lease payments for business property",
        ),
        ("Repairs and maintenance", "21", "Business property and equipment repairs"),
        ("Supplies", "22", "Business supplies not included in COGS"),
        ("Taxes and licenses", "23", "Business taxes and license fees"),
        ("Travel", "24a", "Business travel expenses"),
        ("Meals", "24b", "Business meal expenses"),
        ("Entertainment", "24c", "Business entertainment (state returns only)"),
        ("Utilities", "25", "Business utility expenses"),
        ("Wages", "26", "Wages paid to employees"),
        (
            "Dependent care benefits",
            "27",
            "Dependent care benefits provided to employees",
        ),
    ]

    # Add all categories
    for name, line_number, description in categories:
        IRSExpenseCategory.objects.get_or_create(
            worksheet=worksheet_6a,
            name=name,
            defaults={
                "description": description,
                "line_number": line_number,
                "is_active": True,
            },
        )


def remove_6a_categories(apps, schema_editor):
    IRSWorksheet = apps.get_model("profiles", "IRSWorksheet")
    IRSWorksheet.objects.filter(name="6A").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0032_create_irs_models"),
    ]

    operations = [
        migrations.RunPython(add_6a_categories, remove_6a_categories),
    ]
