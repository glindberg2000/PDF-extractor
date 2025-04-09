#!/usr/bin/env python3
import pandas as pd
import os

print("Transaction Classification Validation")
print("=====================================")

# Load the transaction data
csv_path = os.path.join(
    "data", "clients", "Gene", "output", "csv_sheets", "Gene_all_transactions.csv"
)
df = pd.read_csv(csv_path)

print(f"Total transactions: {len(df)}")
print(f"\nTransactions by worksheet:\n{df.worksheet.value_counts()}")
print(f"\nTransactions by tax_category:\n{df.tax_category.value_counts()}")
print(f"\nTransactions by classification:\n{df.classification.value_counts()}")

# Consistency validation
print("\nConsistency validation:")
inconsistencies = 0

for idx, row in df.iterrows():
    issues = []

    # Check Personal classification consistency
    if row["classification"] == "Personal" and row["business_percentage"] > 0:
        issues.append("Personal classification but business percentage > 0")

    # Check Business classification consistency
    if row["classification"] == "Business" and row["business_percentage"] == 0:
        issues.append("Business classification but business percentage = 0")

    # Check worksheet consistency
    if row["classification"] == "Personal" and row["worksheet"] != "Personal":
        issues.append(f'Personal classification but worksheet is {row["worksheet"]}')

    if row["worksheet"] == "Personal" and row["business_percentage"] > 0:
        issues.append("Personal worksheet but business percentage > 0")

    if row["classification"] == "Business" and row["worksheet"] == "Personal":
        issues.append("Business classification but Personal worksheet")

    # Print any issues found
    if issues:
        inconsistencies += 1
        print(f"\nInconsistencies in Transaction {idx+1}:")
        print(f"Description: {row['description'][:50]}...")
        print(f"Amount: ${row['amount']}")
        print(f"Classification: {row['classification']}")
        print(f"Worksheet: {row['worksheet']}")
        print(f"Business %: {row['business_percentage']}")
        print(f"Tax Category: {row['tax_category']}")
        print("Issues:")
        for issue in issues:
            print(f"- {issue}")

print(f"\nTotal transactions with inconsistencies: {inconsistencies} out of {len(df)}")

if inconsistencies == 0:
    print(
        "\nAll transactions are consistent across classification, worksheet, and business percentage!"
    )

# Check confidence levels
print("\nConfidence level validation:")
low_confidence = df[
    (df["payee_confidence"] == "low")
    | (df["category_confidence"] == "low")
    | (df["classification_confidence"] == "low")
]

if len(low_confidence) > 0:
    print(f"Found {len(low_confidence)} transactions with low confidence:")
    for idx, row in low_confidence.iterrows():
        print(f"\nTransaction {idx+1}:")
        print(f"Description: {row['description'][:50]}...")
        print(f"Payee confidence: {row['payee_confidence']}")
        print(f"Category confidence: {row['category_confidence']}")
        print(f"Classification confidence: {row['classification_confidence']}")
else:
    print("All transactions have medium or high confidence levels!")

# Print detailed transaction logs
print("\nDetailed transaction logs:")
for idx, row in df.iterrows():
    print(f"\nTransaction {idx+1}:")
    print(f"Description: {row['description'][:50]}...")
    print(f"Amount: ${row['amount']}")
    print(f"Pass 1 - Payee: {row['payee']} ({row['payee_confidence']})")
    print(f"Pass 2 - Category: {row['category']} ({row['category_confidence']})")
    print(
        f"Pass 3 - Tax Category: {row['tax_category']} ({row['classification_confidence']})"
    )
    print(f"Classification: {row['classification']}")
    print(f"Worksheet: {row['worksheet']}")
    print(f"Business %: {row['business_percentage']}")
