from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0027_fix_transaction_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql='ALTER TABLE profiles_businessprofile RENAME COLUMN "custom_6A_expense_categories" TO "custom_6a_expense_categories";',
            reverse_sql='ALTER TABLE profiles_businessprofile RENAME COLUMN "custom_6a_expense_categories" TO "custom_6A_expense_categories";',
        ),
    ]
