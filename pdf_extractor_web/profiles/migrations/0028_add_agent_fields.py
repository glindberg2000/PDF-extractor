from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0027_fix_transaction_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="normalized_description",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="payee",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="confidence",
            field=models.CharField(blank=True, max_length=10, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="reasoning",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="business_context",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="transaction",
            name="questions",
            field=models.TextField(blank=True, null=True),
        ),
    ]
