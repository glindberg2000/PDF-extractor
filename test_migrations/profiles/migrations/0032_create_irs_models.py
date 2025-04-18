from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0031_transaction_classification"),
    ]

    operations = [
        migrations.CreateModel(
            name="IRSWorksheet",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255, unique=True)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "IRS Worksheet",
                "verbose_name_plural": "IRS Worksheets",
            },
        ),
        migrations.CreateModel(
            name="IRSExpenseCategory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("line_number", models.CharField(max_length=10)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "worksheet",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="expense_categories",
                        to="profiles.irsworksheet",
                    ),
                ),
            ],
            options={
                "verbose_name": "IRS Expense Category",
                "verbose_name_plural": "IRS Expense Categories",
                "unique_together": {("worksheet", "name")},
            },
        ),
    ]
