from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0041_merge_20250416_2321"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="payee_reasoning",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="payee_extraction_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("AI", "AI Only"),
                    ("AI+Search", "AI with Search"),
                    ("Human", "Human Override"),
                    ("None", "Not Processed"),
                ],
                default=None,
                help_text="Method used to extract the payee information",
                max_length=20,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="transaction",
            name="classification_method",
            field=models.CharField(
                blank=True,
                choices=[
                    ("AI", "AI Classification"),
                    ("Human", "Human Override"),
                    ("None", "Not Processed"),
                ],
                default=None,
                help_text="Method used to classify the transaction",
                max_length=20,
                null=True,
            ),
        ),
    ]
