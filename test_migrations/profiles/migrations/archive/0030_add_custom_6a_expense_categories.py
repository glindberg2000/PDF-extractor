from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0029_import_businessprofile_data"),
    ]

    operations = [
        migrations.AddField(
            model_name="businessprofile",
            name="custom_6A_expense_categories",
            field=models.TextField(blank=True, null=True),
        ),
    ] 