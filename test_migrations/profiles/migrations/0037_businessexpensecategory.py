from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0036_cleanup_businessprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessExpenseCategory",
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
                ("category_name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "tax_year",
                    models.IntegerField(help_text="Tax year this category applies to"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_expense_categories",
                        to="profiles.businessprofile",
                    ),
                ),
                (
                    "parent_category",
                    models.ForeignKey(
                        blank=True,
                        help_text="The IRS category this maps to (e.g., 'Other Expenses' on 6A)",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="profiles.irsexpensecategory",
                    ),
                ),
                (
                    "worksheet",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="business_categories",
                        to="profiles.irsworksheet",
                    ),
                ),
            ],
            options={
                "verbose_name_plural": "Business Expense Categories",
                "unique_together": {("business", "category_name")},
            },
        ),
    ]
