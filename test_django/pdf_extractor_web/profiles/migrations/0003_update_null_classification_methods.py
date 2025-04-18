from django.db import migrations


def update_null_classification_methods(apps, schema_editor):
    Transaction = apps.get_model("profiles", "Transaction")
    Transaction.objects.filter(classification_method__isnull=True).update(
        classification_method="None"
    )


def reverse_update(apps, schema_editor):
    # No need to reverse this data migration
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0002_alter_businessexpensecategory_parent_category_and_more"),
    ]

    operations = [
        migrations.RunPython(
            update_null_classification_methods, reverse_code=reverse_update
        ),
    ]
