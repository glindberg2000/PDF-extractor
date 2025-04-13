from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0034_merge_migrations"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE profiles_businessprofile
            ADD CONSTRAINT profiles_businessprofile_client_id_key UNIQUE (client_id);
            """,
            reverse_sql="""
            ALTER TABLE profiles_businessprofile
            DROP CONSTRAINT IF EXISTS profiles_businessprofile_client_id_key;
            """,
        ),
    ]
