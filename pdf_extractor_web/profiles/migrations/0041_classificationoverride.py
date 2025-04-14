from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0040_update_model_options"),
    ]

    operations = [
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
                ("new_classification_type", models.CharField(max_length=50)),
                ("new_worksheet", models.CharField(max_length=50)),
                ("notes", models.TextField(blank=True)),
                ("created_by", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                (
                    "original_classification",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="overrides",
                        to="profiles.transactionclassification",
                    ),
                ),
                (
                    "transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="classification_overrides",
                        to="profiles.transaction",
                    ),
                ),
            ],
            options={
                "verbose_name": "Classification Override",
                "verbose_name_plural": "Classification Overrides",
                "ordering": ["-created_at"],
            },
        ),
    ]
