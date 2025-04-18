from django.db import migrations


def reset_processing_methods(apps, schema_editor):
    Transaction = apps.get_model("profiles", "Transaction")
    # Reset all processing methods
    Transaction.objects.all().update(
        payee_extraction_method=None, classification_method=None
    )


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0046_add_payee_field"),
    ]

    operations = [
        migrations.RunPython(reset_processing_methods),
    ]
