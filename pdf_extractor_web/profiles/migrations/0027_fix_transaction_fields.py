from django.db import migrations
import django.contrib.postgres.fields.jsonb


def migrate_transaction_data(apps, schema_editor):
    cursor = schema_editor.connection.cursor()

    # Create minimal BusinessProfile table
    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS profiles_businessprofile (
        id SERIAL PRIMARY KEY,
        client_id VARCHAR(255) NOT NULL UNIQUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Insert a default profile for existing transactions
    INSERT INTO profiles_businessprofile (client_id) VALUES ('5')
    ON CONFLICT (client_id) DO NOTHING;
    """
    )

    # Create transaction table
    cursor.execute(
        """
        CREATE TABLE profiles_transaction (
            id SERIAL PRIMARY KEY,
            client_id VARCHAR(255) NOT NULL REFERENCES profiles_businessprofile(client_id),
            transaction_date DATE NOT NULL,
            amount DECIMAL(10, 2) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(255),
            parsed_data JSONB DEFAULT '{}',
            file_path VARCHAR(255),
            source VARCHAR(255),
            transaction_type VARCHAR(50),
            normalized_amount DECIMAL(10, 2),
            statement_start_date DATE,
            statement_end_date DATE,
            account_number VARCHAR(50),
            transaction_id INTEGER UNIQUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """
    )

    # Create normalized vendor data table
    cursor.execute(
        """
        CREATE TABLE profiles_normalizedvendordata (
            id SERIAL PRIMARY KEY,
            transaction_id INTEGER NOT NULL REFERENCES profiles_transaction(id),
            normalized_name VARCHAR(255) NOT NULL,
            normalized_description TEXT,
            justification TEXT,
            confidence NUMERIC(5, 4) NOT NULL,
            tools_used JSONB DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """
    )

    # Create indexes
    cursor.execute(
        """
        CREATE INDEX idx_transaction_client_id ON profiles_transaction(client_id);
        CREATE INDEX idx_transaction_date ON profiles_transaction(transaction_date);
        CREATE INDEX idx_transaction_id ON profiles_transaction(transaction_id);
        CREATE INDEX idx_normalized_vendor_transaction_id ON profiles_normalizedvendordata(transaction_id);
    """
    )


def reverse_migrate(apps, schema_editor):
    cursor = schema_editor.connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS profiles_normalizedvendordata")
    cursor.execute("DROP TABLE IF EXISTS profiles_transaction")
    cursor.execute("DROP TABLE IF EXISTS profiles_businessprofile")


class Migration(migrations.Migration):

    dependencies = [
        ("profiles", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(migrate_transaction_data, reverse_migrate),
    ]
