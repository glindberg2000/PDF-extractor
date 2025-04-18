from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0037_businessexpensecategory"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="transaction",
            options={"ordering": ["-date"]},
        ),
        migrations.CreateModel(
            name="ClassificationOverride",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "classification_type",
                    models.CharField(
                        choices=[
                            ("income", "Income"),
                            ("expense", "Expense"),
                            ("transfer", "Transfer"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "worksheet",
                    models.CharField(
                        choices=[
                            ("6a", "6a"),
                            ("6b", "6b"),
                            ("6c", "6c"),
                            ("6d", "6d"),
                            ("6e", "6e"),
                            ("6f", "6f"),
                            ("6g", "6g"),
                            ("6h", "6h"),
                            ("6i", "6i"),
                            ("6j", "6j"),
                            ("6k", "6k"),
                            ("6l", "6l"),
                            ("6m", "6m"),
                            ("6n", "6n"),
                            ("6o", "6o"),
                            ("6p", "6p"),
                            ("6q", "6q"),
                            ("6r", "6r"),
                            ("6s", "6s"),
                            ("6t", "6t"),
                            ("6u", "6u"),
                            ("6v", "6v"),
                            ("6w", "6w"),
                            ("6x", "6x"),
                            ("6y", "6y"),
                            ("6z", "6z"),
                        ],
                        max_length=20,
                    ),
                ),
                ("reasoning", models.TextField()),
                (
                    "transaction",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classification_override",
                        to="profiles.transaction",
                    ),
                ),
            ],
            options={
                "abstract": False,
            },
        ),
    ]
