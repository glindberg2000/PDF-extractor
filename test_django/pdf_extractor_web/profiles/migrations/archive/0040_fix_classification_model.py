from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0039_merge_20250416_0051"),
    ]

    operations = [
        # Drop the column if it exists
        migrations.RunSQL(
            sql="""
                ALTER TABLE profiles_classificationoverride 
                DROP COLUMN IF EXISTS original_classification_id;
            """,
            reverse_sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'profiles_classificationoverride' 
                        AND column_name = 'original_classification_id'
                    ) THEN
                        ALTER TABLE profiles_classificationoverride 
                        ADD COLUMN original_classification_id integer 
                        REFERENCES profiles_transactionclassification(id) 
                        ON DELETE CASCADE;
                    END IF;
                END $$;
            """
        ),
        # Then remove the TransactionClassification model
        migrations.DeleteModel(
            name="TransactionClassification",
        ),
        # Add fields to Transaction if they don't exist
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'profiles_transaction' 
                        AND column_name = 'classification_type'
                    ) THEN
                        ALTER TABLE profiles_transaction 
                        ADD COLUMN classification_type varchar(50) NULL;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'profiles_transaction' 
                        AND column_name = 'worksheet'
                    ) THEN
                        ALTER TABLE profiles_transaction 
                        ADD COLUMN worksheet varchar(50) NULL;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'profiles_transaction' 
                        AND column_name = 'business_percentage'
                    ) THEN
                        ALTER TABLE profiles_transaction 
                        ADD COLUMN business_percentage integer NOT NULL DEFAULT 100;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'profiles_transaction' 
                        AND column_name = 'classification_method'
                    ) THEN
                        ALTER TABLE profiles_transaction 
                        ADD COLUMN classification_method varchar(50) NULL;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'profiles_transaction' 
                        AND column_name = 'payee_extraction_method'
                    ) THEN
                        ALTER TABLE profiles_transaction 
                        ADD COLUMN payee_extraction_method varchar(50) NULL;
                    END IF;
                END $$;
            """,
            reverse_sql="""
                ALTER TABLE profiles_transaction 
                DROP COLUMN IF EXISTS classification_type,
                DROP COLUMN IF EXISTS worksheet,
                DROP COLUMN IF EXISTS business_percentage,
                DROP COLUMN IF EXISTS classification_method,
                DROP COLUMN IF EXISTS payee_extraction_method;
            """
        ),
    ]
