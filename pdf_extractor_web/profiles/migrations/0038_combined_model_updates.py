from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0037_businessexpensecategory"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="transaction",
            options={"ordering": ["-date"]},
        ),
        migrations.RunSQL(
            sql="""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'profiles_classificationoverride'
                ) THEN
                    CREATE TABLE profiles_classificationoverride (
                        id bigserial NOT NULL PRIMARY KEY,
                        created_at timestamp with time zone NOT NULL,
                        updated_at timestamp with time zone NOT NULL,
                        classification_type varchar(20) NOT NULL,
                        worksheet varchar(20) NOT NULL,
                        reasoning text NOT NULL,
                        transaction_id bigint NOT NULL REFERENCES profiles_transaction(id) ON DELETE CASCADE
                    );

                    CREATE INDEX profiles_classificationoverride_transaction_id_idx
                    ON profiles_classificationoverride(transaction_id);

                    ALTER TABLE profiles_classificationoverride
                    ADD CONSTRAINT profiles_classificationoverride_transaction_id_key
                    UNIQUE (transaction_id);
                END IF;
            END $$;
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS profiles_classificationoverride;
            """,
        ),
    ]
