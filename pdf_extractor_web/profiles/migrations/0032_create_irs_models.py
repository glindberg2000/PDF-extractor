from django.db import migrations, models
from django.db.migrations.operations.base import Operation


class CheckTableExists(Operation):
    def __init__(self, table_name):
        self.table_name = table_name

    def state_forwards(self, app_label, state):
        pass

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        schema_editor.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{self.table_name}'
                ) THEN
                    RAISE NOTICE 'Table % already exists', '{self.table_name}';
                ELSE
                    RAISE NOTICE 'Table % does not exist', '{self.table_name}';
                END IF;
            END $$;
            """
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass

    def describe(self):
        return f"Checks if table {self.table_name} exists"


class Migration(migrations.Migration):
    dependencies = [
        ("profiles", "0031_transaction_classification"),
    ]

    operations = [
        CheckTableExists("profiles_irsworksheet"),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS profiles_irsworksheet (
                id bigserial PRIMARY KEY,
                name varchar(255) UNIQUE NOT NULL,
                description text,
                is_active boolean NOT NULL DEFAULT true,
                created_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS profiles_irsworksheet;",
        ),
        CheckTableExists("profiles_irsexpensecategory"),
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS profiles_irsexpensecategory (
                id bigserial PRIMARY KEY,
                name varchar(255) NOT NULL,
                description text,
                line_number varchar(10) NOT NULL,
                is_active boolean NOT NULL DEFAULT true,
                created_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at timestamp with time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
                worksheet_id bigint REFERENCES profiles_irsworksheet(id) ON DELETE CASCADE,
                UNIQUE(worksheet_id, name)
            );
            """,
            reverse_sql="DROP TABLE IF EXISTS profiles_irsexpensecategory;",
        ),
    ]
