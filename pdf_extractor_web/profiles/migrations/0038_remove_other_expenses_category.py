from django.db import migrations


def remove_other_expenses_category(apps, schema_editor):
    IRSExpenseCategory = apps.get_model("profiles", "IRSExpenseCategory")
    IRSWorksheet = apps.get_model("profiles", "IRSWorksheet")

    # Get the 6A worksheet
    worksheet_6a = IRSWorksheet.objects.get(name="6A")

    # Remove the "Other Expenses" category if it exists
    IRSExpenseCategory.objects.filter(
        worksheet=worksheet_6a, name="Other Expenses"
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0037_businessexpensecategory"),
    ]

    operations = [
        migrations.RunPython(remove_other_expenses_category),
    ]
