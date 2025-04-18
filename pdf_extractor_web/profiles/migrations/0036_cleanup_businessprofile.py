from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0035_businessprofile_unique"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Drop foreign key constraints
            ALTER TABLE profiles_clientexpensecategory
            DROP CONSTRAINT IF EXISTS profiles_clientexpen_client_id_3aab47cd_fk_profiles_;

            ALTER TABLE profiles_transaction
            DROP CONSTRAINT IF EXISTS profiles_transaction_client_id_117e8684_fk_profiles_;

            ALTER TABLE profiles_processingtask
            DROP CONSTRAINT IF EXISTS profiles_processingt_client_id_134d18bd_fk_profiles_;

            -- Drop any existing constraints on BusinessProfile
            ALTER TABLE profiles_businessprofile
            DROP CONSTRAINT IF EXISTS profiles_businessprofile_pkey;
            
            ALTER TABLE profiles_businessprofile
            DROP CONSTRAINT IF EXISTS profiles_businessprofile_client_id_key;
            
            -- Add the primary key constraint
            ALTER TABLE profiles_businessprofile
            ADD PRIMARY KEY (client_id);

            -- Recreate foreign key constraints
            ALTER TABLE profiles_clientexpensecategory
            ADD CONSTRAINT profiles_clientexpen_client_id_3aab47cd_fk_profiles_
            FOREIGN KEY (client_id) REFERENCES profiles_businessprofile(client_id)
            ON DELETE CASCADE;

            ALTER TABLE profiles_transaction
            ADD CONSTRAINT profiles_transaction_client_id_117e8684_fk_profiles_
            FOREIGN KEY (client_id) REFERENCES profiles_businessprofile(client_id)
            ON DELETE CASCADE;

            ALTER TABLE profiles_processingtask
            ADD CONSTRAINT profiles_processingt_client_id_134d18bd_fk_profiles_
            FOREIGN KEY (client_id) REFERENCES profiles_businessprofile(client_id)
            ON DELETE CASCADE;
            """,
            reverse_sql="""
            -- Drop foreign key constraints
            ALTER TABLE profiles_clientexpensecategory
            DROP CONSTRAINT IF EXISTS profiles_clientexpen_client_id_3aab47cd_fk_profiles_;

            ALTER TABLE profiles_transaction
            DROP CONSTRAINT IF EXISTS profiles_transaction_client_id_117e8684_fk_profiles_;

            ALTER TABLE profiles_processingtask
            DROP CONSTRAINT IF EXISTS profiles_processingt_client_id_134d18bd_fk_profiles_;

            -- Drop primary key constraint
            ALTER TABLE profiles_businessprofile
            DROP CONSTRAINT IF EXISTS profiles_businessprofile_pkey;

            -- Recreate foreign key constraints with old primary key
            ALTER TABLE profiles_clientexpensecategory
            ADD CONSTRAINT profiles_clientexpen_client_id_3aab47cd_fk_profiles_
            FOREIGN KEY (client_id) REFERENCES profiles_businessprofile(id)
            ON DELETE CASCADE;

            ALTER TABLE profiles_transaction
            ADD CONSTRAINT profiles_transaction_client_id_117e8684_fk_profiles_
            FOREIGN KEY (client_id) REFERENCES profiles_businessprofile(id)
            ON DELETE CASCADE;

            ALTER TABLE profiles_processingtask
            ADD CONSTRAINT profiles_processingt_client_id_134d18bd_fk_profiles_
            FOREIGN KEY (client_id) REFERENCES profiles_businessprofile(id)
            ON DELETE CASCADE;
            """,
        ),
    ]
