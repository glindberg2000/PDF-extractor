from django.db import migrations


def import_businessprofile_data(apps, schema_editor):
    cursor = schema_editor.connection.cursor()

    # Insert the business profile data
    cursor.execute(
        """
        INSERT INTO profiles_businessprofile (
            client_id,
            business_type,
            business_description,
            common_business_expenses,
            custom_6A_expense_categories,
            created_at,
            updated_at
        ) VALUES (
            '5',
            'Real Estate Agent',
            'Local Residential Real Estate sales agent',
            '["Advertising", "Car and truck expenses", "Commissions and fees", "Contract labor", "Depletion", "Employee benefit programs", "Insurance (other than health)", "Interest (mortgage/other)", "Legal and professional services", "Office expenses", "Pension and profit-sharing plans", "Rent or lease (vehicles/equipment/other)", "Repairs and maintenance", "Supplies", "Taxes and licenses", "Travel, meals, and entertainment", "Utilities", "Wages", "Other expenses"]',
            '["Due and Subscriptions", "MLS Dues", "Open House Expense", "Staging", "Computer & Internet"]',
            '2025-04-10 18:27:35',
            '2025-04-10 18:27:35'
        );
    """
    )


def reverse_import(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    cursor.execute("DELETE FROM profiles_businessprofile WHERE client_id = '5';")


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0028_transform_businessprofile_data"),
    ]

    operations = [
        migrations.RunPython(import_businessprofile_data, reverse_import),
    ]
