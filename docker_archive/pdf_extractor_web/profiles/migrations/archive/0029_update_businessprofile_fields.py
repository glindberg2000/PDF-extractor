from django.db import migrations, models
from django.db.models import JSONField


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0028_rename_custom_6A_expense_categories"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name="businessprofile",
                    name="common_expenses",
                    field=JSONField(default=dict),
                ),
                migrations.AddField(
                    model_name="businessprofile",
                    name="custom_6a_categories",
                    field=JSONField(default=dict),
                ),
                migrations.AddField(
                    model_name="businessprofile",
                    name="industry_keywords",
                    field=JSONField(default=dict),
                ),
                migrations.AddField(
                    model_name="businessprofile",
                    name="category_patterns",
                    field=JSONField(default=dict),
                ),
                migrations.AddField(
                    model_name="businessprofile",
                    name="profile_data",
                    field=JSONField(default=dict),
                ),
                migrations.AddField(
                    model_name="businessprofile",
                    name="generated_profile",
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name="businessprofile",
                    name="location",
                    field=models.CharField(blank=True, max_length=200, null=True),
                ),
            ],
        ),
    ]
