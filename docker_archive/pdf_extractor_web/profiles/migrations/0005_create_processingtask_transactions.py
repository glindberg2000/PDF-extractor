from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0004_alter_transaction_classification_method_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProcessingTaskTransaction",
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
                    "processingtask",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, to="profiles.processingtask"
                    ),
                ),
                (
                    "transaction",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, to="profiles.transaction"
                    ),
                ),
            ],
            options={
                "db_table": "profiles_processingtask_transactions",
                "unique_together": {("processingtask", "transaction")},
            },
        ),
    ]
