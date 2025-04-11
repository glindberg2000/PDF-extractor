from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0010_normalizedvendordata_original_context_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tool",
            name="code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tool",
            name="created_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name="tool",
            name="is_active",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="tool",
            name="schema",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tool",
            name="updated_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="tool",
            name="module_path",
            field=models.CharField(max_length=255, blank=True, null=True),
        ),
        # Update existing records with current timestamps
        migrations.RunSQL(
            sql=[
                "UPDATE profiles_tool SET created_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE created_at IS NULL",
            ],
            reverse_sql=[],
        ),
        # Make the fields non-nullable
        migrations.AlterField(
            model_name="tool",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name="tool",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
