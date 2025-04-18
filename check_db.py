#!/usr/bin/env python3
import sqlite3
import os
import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

print("Database Structure Check")
print("=======================")

# List of database files to check
db_files = [
    os.path.join("dataextractai", "db", "client.db"),
    os.path.join("data", "clients", "Gene", "gene.db"),
    os.path.join("data", "clients", "client_data.db"),
    os.path.join("data", "db", "clients.db"),
]

for db_path in db_files:
    if not os.path.exists(db_path):
        print(f"\nDatabase file not found: {db_path}")
        continue

    print(f"\n\nChecking database: {db_path}")
    print("=" * (len(db_path) + 19))

    try:
        conn = sqlite3.connect(db_path)

        # Get all tables
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(f"No tables found in database: {db_path}")
            continue

        print(f"Tables in database: {[table[0] for table in tables]}")

        # Look for specific tables we're interested in
        target_tables = [
            "transaction_classifications",
            "tax_categories",
            "normalized_transactions",
        ]

        for target in target_tables:
            if any(table[0] == target for table in tables):
                table_name = target
                print(f"\n{table_name} Table Structure:")

                # Get table structure
                cursor = conn.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()

                for col in columns:
                    print(f"  {col[1]} ({col[2]})")

                # Get sample data
                cursor = conn.execute(f"SELECT * FROM {table_name} LIMIT 3")
                sample_data = cursor.fetchall()

                if sample_data:
                    print(f"\nSample data from {table_name}:")
                    # Get column names
                    column_names = [
                        description[0] for description in cursor.description
                    ]

                    # Create a DataFrame for nicer display
                    df = pd.DataFrame(sample_data, columns=column_names)

                    # For large tables, only show key columns
                    if len(df.columns) > 10:
                        if table_name == "transaction_classifications":
                            important_cols = [
                                "transaction_id",
                                "payee",
                                "category",
                                "tax_category_id",
                                "worksheet",
                                "business_percentage",
                                "classification",
                            ]
                        elif table_name == "normalized_transactions":
                            important_cols = [
                                "transaction_id",
                                "transaction_date",
                                "description",
                                "amount",
                            ]
                        elif table_name == "tax_categories":
                            important_cols = ["id", "name", "worksheet", "is_personal"]
                        else:
                            important_cols = df.columns[:5].tolist()

                        subset_cols = [
                            col for col in important_cols if col in df.columns
                        ]
                        print(df[subset_cols].to_string())
                    else:
                        print(df.to_string())
                else:
                    print(f"No data found in {table_name} table")

        conn.close()

    except Exception as e:
        print(f"Error accessing database {db_path}: {e}")
        continue

# Database connection parameters
db_params = {
    "dbname": "mydatabase",
    "user": "newuser",
    "password": "newpassword",
    "host": "localhost",
    "port": "5432",
}


def check_database():
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_params)
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Check transaction table structure
        print("\nTransaction table structure:")
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'profiles_transaction'
            ORDER BY ordinal_position;
        """
        )
        for row in cur.fetchall():
            print(
                f"{row['column_name']}: {row['data_type']} (nullable: {row['is_nullable']})"
            )

        # Check if payee field exists and has data
        print("\nChecking payee field data:")
        cur.execute(
            """
            SELECT COUNT(*) as total,
                   COUNT(payee) as has_payee,
                   COUNT(CASE WHEN payee IS NOT NULL THEN 1 END) as non_null_payee
            FROM profiles_transaction;
        """
        )
        payee_stats = cur.fetchone()
        print(f"Total records: {payee_stats['total']}")
        print(f"Records with payee field: {payee_stats['has_payee']}")
        print(f"Records with non-null payee: {payee_stats['non_null_payee']}")

        # Check applied migrations
        print("\nApplied migrations:")
        cur.execute(
            """
            SELECT id, name, applied 
            FROM django_migrations 
            WHERE app = 'profiles' 
            ORDER BY id;
        """
        )
        for row in cur.fetchall():
            print(f"{row['id']}: {row['name']} (applied: {row['applied']})")

        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    check_database()
