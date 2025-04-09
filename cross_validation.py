#!/usr/bin/env python3
import sqlite3
import pandas as pd
import os

print("Transaction Cross-Validation")
print("===========================")

# Load the database transactions
db_path = os.path.join("data", "db", "clients.db")
conn = sqlite3.connect(db_path)

# Get transaction classifications from database
db_query = """
SELECT 
    tc.transaction_id,
    tc.payee,
    tc.category,
    tc.classification,
    tc.worksheet,
    tc.business_percentage,
    tc.tax_category_id,
    tc.expense_type,
    nt.description,
    nt.amount,
    c.name as client_name
FROM 
    transaction_classifications tc
JOIN 
    normalized_transactions nt ON tc.transaction_id = nt.transaction_id AND tc.client_id = nt.client_id
JOIN
    clients c ON tc.client_id = c.id
WHERE
    c.name = 'Gene'
"""

# Load transactions from database
db_df = pd.read_sql_query(db_query, conn)
print(f"Loaded {len(db_df)} transactions from database")

# Load transactions from CSV export
csv_path = os.path.join(
    "data", "clients", "Gene", "output", "csv_sheets", "Gene_all_transactions.csv"
)
csv_df = pd.read_csv(csv_path)
print(f"Loaded {len(csv_df)} transactions from CSV export")

# Validation checks
print("\nRunning validation checks...")

# Check 1: Personal expense validation
personal_check_db = db_df[
    (db_df["classification"] == "Personal") & (db_df["worksheet"] != "Personal")
]
personal_check_csv = csv_df[
    (csv_df["classification"] == "Personal") & (csv_df["worksheet"] != "Personal")
]

if len(personal_check_db) > 0:
    print(
        f"\nWARNING: Found {len(personal_check_db)} transactions in database with 'Personal' classification but non-Personal worksheet"
    )
    print(
        personal_check_db[
            ["transaction_id", "description", "classification", "worksheet"]
        ].to_string()
    )
else:
    print("✓ All Personal expenses in database have correct worksheet")

if len(personal_check_csv) > 0:
    print(
        f"\nWARNING: Found {len(personal_check_csv)} transactions in CSV with 'Personal' classification but non-Personal worksheet"
    )
    print(
        personal_check_csv[
            ["transaction_id", "description", "classification", "worksheet"]
        ].to_string()
    )
else:
    print("✓ All Personal expenses in CSV have correct worksheet")

# Check 2: Business percentage validation
biz_check_db = db_df[
    (db_df["classification"] == "Personal") & (db_df["business_percentage"] > 0)
]
biz_check_csv = csv_df[
    (csv_df["classification"] == "Personal") & (csv_df["business_percentage"] > 0)
]

if len(biz_check_db) > 0:
    print(
        f"\nWARNING: Found {len(biz_check_db)} transactions in database with 'Personal' classification but business_percentage > 0"
    )
    print(
        biz_check_db[
            ["transaction_id", "description", "classification", "business_percentage"]
        ].to_string()
    )
else:
    print("✓ All Personal expenses in database have business_percentage = 0")

if len(biz_check_csv) > 0:
    print(
        f"\nWARNING: Found {len(biz_check_csv)} transactions in CSV with 'Personal' classification but business_percentage > 0"
    )
    print(
        biz_check_csv[
            ["transaction_id", "description", "classification", "business_percentage"]
        ].to_string()
    )
else:
    print("✓ All Personal expenses in CSV have business_percentage = 0")

# Check 3: Check for mismatches between database and CSV export
if len(db_df) == len(csv_df):
    # Sort both DFs by transaction_id to ensure proper comparison
    db_df = db_df.sort_values("transaction_id").reset_index(drop=True)
    csv_df = csv_df.sort_values("transaction_id").reset_index(drop=True)

    # Check for key field mismatches
    compare_fields = [
        "worksheet",
        "classification",
        "business_percentage",
        "tax_category_id",
    ]

    for field in compare_fields:
        if field in csv_df.columns and field in db_df.columns:
            mismatches = db_df[db_df[field] != csv_df[field]]
            if len(mismatches) > 0:
                print(
                    f"\nWARNING: Found {len(mismatches)} mismatches in '{field}' between database and CSV export"
                )
                for idx, row in mismatches.iterrows():
                    print(
                        f"Transaction {row['transaction_id']}: DB={row[field]}, CSV={csv_df.loc[idx, field]}"
                    )
            else:
                print(f"✓ Field '{field}' matches between database and CSV export")
        else:
            print(f"Field '{field}' not found in both datasets")
else:
    print(
        f"\nWARNING: Database has {len(db_df)} transactions but CSV export has {len(csv_df)}"
    )

print("\nValidation complete!")
conn.close()
