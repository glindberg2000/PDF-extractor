from django.db import migrations


def fix_processing_methods(apps, schema_editor):
    Transaction = apps.get_model("profiles", "Transaction")
    # First, set all records without a payee to None
    Transaction.objects.filter(payee__isnull=True).update(payee_extraction_method=None)
    # Then, set records with a payee but no method to AI Only
    Transaction.objects.filter(
        payee__isnull=False, payee_extraction_method__isnull=True
    ).update(payee_extraction_method="AI")


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0047_reset_processing_methods"),
    ]

    operations = [
        migrations.RunPython(fix_processing_methods),
    ]
