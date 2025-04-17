from django.db import migrations


def reset_processing_methods(apps, schema_editor):
    Transaction = apps.get_model("profiles", "Transaction")
    # Reset all records that don't have a payee or classification
    Transaction.objects.filter(
        payee__isnull=True, classification_type__isnull=True
    ).update(payee_extraction_method=None, classification_method=None)


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0043_auto_20250416_2358"),
    ]

    operations = [
        migrations.RunPython(reset_processing_methods),
    ]
