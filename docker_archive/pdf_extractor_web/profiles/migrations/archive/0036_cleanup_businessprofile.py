from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0035_businessprofile_unique"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Drop any existing constraints
            ALTER TABLE profiles_businessprofile
            DROP CONSTRAINT IF EXISTS profiles_businessprofile_pkey;
            
            ALTER TABLE profiles_businessprofile
            DROP CONSTRAINT IF EXISTS profiles_businessprofile_client_id_key;
            
            -- Add the primary key constraint
            ALTER TABLE profiles_businessprofile
            ADD PRIMARY KEY (client_id);
            """,
            reverse_sql="""
            ALTER TABLE profiles_businessprofile
            DROP CONSTRAINT IF EXISTS profiles_businessprofile_pkey;
            """,
        ),
    ]
