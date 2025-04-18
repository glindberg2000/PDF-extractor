from django.db import migrations


def add_tim_and_gene_profile(apps, schema_editor):
    BusinessProfile = apps.get_model("profiles", "BusinessProfile")
    ClientExpenseCategory = apps.get_model("profiles", "ClientExpenseCategory")
    IRSWorksheet = apps.get_model("profiles", "IRSWorksheet")
    IRSExpenseCategory = apps.get_model("profiles", "IRSExpenseCategory")

    # Create the business profile
    profile = BusinessProfile.objects.create(
        client_id="Tim and Gene",
        business_type="realtor",
        business_percentage=100.0,
        additional_info={
            "business_description": "Real Estate Brokerage",
            "primary_activities": [
                "Property sales",
                "Property management",
                "Real estate consulting",
            ],
            "business_start_date": "2020-01-01",
        },
    )

    # Get or create the Schedule C worksheet
    worksheet, _ = IRSWorksheet.objects.get_or_create(
        name="Schedule C", description="Profit or Loss from Business"
    )

    # Create realtor-specific expense categories
    categories = [
        {
            "name": "Advertising",
            "description": "Marketing and promotional expenses",
            "parent_category": None,
        },
        {
            "name": "Car and Truck Expenses",
            "description": "Vehicle expenses for business use",
            "parent_category": None,
        },
        {
            "name": "Commissions and Fees",
            "description": "Real estate commissions and referral fees",
            "parent_category": None,
        },
        {
            "name": "Insurance",
            "description": "Business insurance premiums",
            "parent_category": None,
        },
        {
            "name": "Legal and Professional Services",
            "description": "Attorney and accounting fees",
            "parent_category": None,
        },
        {
            "name": "Office Expenses",
            "description": "Office supplies and equipment",
            "parent_category": None,
        },
        {
            "name": "Rent or Lease",
            "description": "Office space and equipment rental",
            "parent_category": None,
        },
        {
            "name": "Repairs and Maintenance",
            "description": "Office and equipment maintenance",
            "parent_category": None,
        },
        {
            "name": "Supplies",
            "description": "Office and business supplies",
            "parent_category": None,
        },
        {
            "name": "Taxes and Licenses",
            "description": "Business licenses and taxes",
            "parent_category": None,
        },
        {
            "name": "Travel",
            "description": "Business travel expenses",
            "parent_category": None,
        },
        {
            "name": "Meals and Entertainment",
            "description": "Business meals and entertainment",
            "parent_category": None,
        },
        {
            "name": "Utilities",
            "description": "Office utilities",
            "parent_category": None,
        },
        {
            "name": "Wages",
            "description": "Employee wages and benefits",
            "parent_category": None,
        },
        {
            "name": "Other Expenses",
            "description": "Miscellaneous business expenses",
            "parent_category": None,
        },
    ]

    # Create the expense categories
    for category_data in categories:
        category = ClientExpenseCategory.objects.create(
            client=profile,
            category_name=category_data["name"],
            category_type="expense",
            description=category_data["description"],
            irs_worksheet=worksheet,
        )

        # Create corresponding IRS expense category if it doesn't exist
        irs_category, _ = IRSExpenseCategory.objects.get_or_create(
            name=category_data["name"],
            description=category_data["description"],
            worksheet=worksheet,
        )


def remove_tim_and_gene_profile(apps, schema_editor):
    BusinessProfile = apps.get_model("profiles", "BusinessProfile")
    BusinessProfile.objects.filter(client_id="Tim and Gene").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0053_add_realtor_business_categories"),
    ]

    operations = [
        migrations.RunPython(add_tim_and_gene_profile, remove_tim_and_gene_profile),
    ]
