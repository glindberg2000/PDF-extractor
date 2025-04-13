from django.db import migrations
from django.db.models import JSONField
import json


def migrate_data(apps, schema_editor):
    # First, add the new columns
    schema_editor.execute(
        """
        ALTER TABLE profiles_businessprofile
        ADD COLUMN IF NOT EXISTS common_expenses JSONB DEFAULT '{}',
        ADD COLUMN IF NOT EXISTS custom_categories JSONB DEFAULT '{}',
        ADD COLUMN IF NOT EXISTS industry_keywords JSONB DEFAULT '{}',
        ADD COLUMN IF NOT EXISTS category_patterns JSONB DEFAULT '{}',
        ADD COLUMN IF NOT EXISTS profile_data JSONB DEFAULT '{}'
    """
    )

    # Then migrate the data
    schema_editor.execute(
        """
        UPDATE profiles_businessprofile
        SET common_expenses = CASE
            WHEN common_business_expenses IS NOT NULL AND common_business_expenses != ''
            THEN jsonb_build_object('expenses', CASE
                WHEN common_business_expenses::jsonb IS NOT NULL
                THEN common_business_expenses::jsonb
                ELSE jsonb_build_array(common_business_expenses)
                END)
            ELSE '{}'::jsonb
            END,
        custom_categories = CASE
            WHEN custom_6a_expense_categories IS NOT NULL AND custom_6a_expense_categories != ''
            THEN jsonb_build_object('categories', CASE
                WHEN custom_6a_expense_categories::jsonb IS NOT NULL
                THEN custom_6a_expense_categories::jsonb
                ELSE jsonb_build_array(custom_6a_expense_categories)
                END)
            ELSE '{}'::jsonb
            END
    """
    )


def reverse_migrate(apps, schema_editor):
    # Reverse migrate the data
    schema_editor.execute(
        """
        UPDATE profiles_businessprofile
        SET common_business_expenses = CASE
            WHEN common_expenses ? 'expenses'
            THEN common_expenses->>'expenses'
            ELSE NULL
            END,
        custom_6a_expense_categories = CASE
            WHEN custom_categories ? 'categories'
            THEN custom_categories->>'categories'
            ELSE NULL
            END
    """
    )

    # Drop the new columns
    schema_editor.execute(
        """
        ALTER TABLE profiles_businessprofile
        DROP COLUMN IF EXISTS common_expenses,
        DROP COLUMN IF EXISTS custom_categories,
        DROP COLUMN IF EXISTS industry_keywords,
        DROP COLUMN IF EXISTS category_patterns,
        DROP COLUMN IF EXISTS profile_data
    """
    )


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0031_transaction_classification"),
    ]

    operations = [
        migrations.RunPython(migrate_data, reverse_migrate),
    ]
