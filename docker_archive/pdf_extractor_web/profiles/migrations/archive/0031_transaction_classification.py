from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0030_merge_20250412_0320"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transaction",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.CreateModel(
            name="TransactionClassification",
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
                (
                    "classification_type",
                    models.CharField(
                        help_text="Type of classification (e.g., 'business', 'personal')",
                        max_length=50,
                    ),
                ),
                (
                    "worksheet",
                    models.CharField(
                        help_text="Tax worksheet category (e.g., '6A', 'Auto', 'HomeOffice')",
                        max_length=50,
                    ),
                ),
                (
                    "confidence",
                    models.CharField(
                        help_text="Confidence level of the classification",
                        max_length=20,
                    ),
                ),
                (
                    "reasoning",
                    models.TextField(
                        help_text="Explanation for the classification decision"
                    ),
                ),
                (
                    "created_by",
                    models.CharField(
                        help_text="Agent or user who created this classification",
                        max_length=100,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this is the current active classification",
                    ),
                ),
                (
                    "transaction",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="classifications",
                        to="profiles.transaction",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["transaction", "created_at"],
                        name="profiles_tr_transac_0e6ed3_idx",
                    ),
                    models.Index(
                        fields=["transaction", "is_active"],
                        name="profiles_tr_transac_2c9442_idx",
                    ),
                    models.Index(
                        fields=["classification_type"],
                        name="profiles_tr_classif_1458d9_idx",
                    ),
                    models.Index(
                        fields=["worksheet"], name="profiles_tr_workshe_d85d76_idx"
                    ),
                ],
            },
        ),
        migrations.AlterField(
            model_name="transaction",
            name="confidence",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
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
                ("name", models.CharField(max_length=50, unique=True)),
                ("description", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
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
                ("description", models.TextField()),
                (
                    "line_number",
                    models.CharField(
                        help_text="Line number on the IRS form", max_length=50
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "worksheet",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="categories",
                        to="profiles.irsworksheet",
                    ),
                ),
            ],
            options={
                "ordering": ["worksheet", "line_number"],
                "unique_together": {("worksheet", "name")},
            },
        ),
    ]
