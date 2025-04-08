import pandas as pd
import sqlite3
import logging
from dataextractai.agents.transaction_classifier import TransactionClassifier

# Set up logging
logging.basicConfig(level=logging.INFO)


def process_main_db():
    # Connect to the main database
    db_path = "data/db/clients.db"

    # Load unprocessed transactions from the database
    with sqlite3.connect(db_path) as conn:
        query = """
        SELECT nt.transaction_id, nt.description, nt.amount, nt.transaction_date
        FROM normalized_transactions nt
        LEFT JOIN transaction_classifications tc ON nt.transaction_id = tc.transaction_id
        WHERE tc.transaction_id IS NULL
        ORDER BY nt.transaction_date DESC
        """
        df = pd.read_sql_query(query, conn)

    if df.empty:
        print("No unprocessed transactions found.")
        return

    print(f"Found {len(df)} unprocessed transactions")

    # Initialize the classifier for the client
    classifier = TransactionClassifier("Gene")  # Replace with actual client name

    # Process the transactions
    stats = classifier.process_transactions(
        df,
        resume_from_pass=1,  # Start from the first pass
        force_process=False,  # Don't force reprocessing of already processed transactions
        batch_size=10,  # Process in batches of 10
    )

    print("\nProcessing complete!")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    process_main_db()
