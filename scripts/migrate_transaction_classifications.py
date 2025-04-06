"""
Migration script to update transaction_classifications table to use client_id instead of client_name.
"""

import sqlite3
import logging
from dataextractai.db.client_db import ClientDB

logger = logging.getLogger(__name__)


def migrate_transaction_classifications():
    """Migrate transaction_classifications table to use client_id."""
    db = ClientDB()

    with sqlite3.connect(db.db_path) as conn:
        cursor = conn.cursor()

        try:
            # Create temporary table with new schema
            cursor.execute(
                """
                CREATE TABLE transaction_classifications_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER NOT NULL,
                    transaction_id TEXT NOT NULL,
                    payee TEXT,
                    payee_confidence TEXT,
                    payee_notes TEXT,
                    category TEXT,
                    base_category TEXT,
                    category_confidence TEXT,
                    category_notes TEXT,
                    expense_type TEXT CHECK(expense_type IN ('business', 'personal', 'unclassified')),
                    business_percentage INTEGER CHECK(business_percentage BETWEEN 0 AND 100),
                    business_confidence TEXT,
                    business_notes TEXT,
                    required_documentation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    UNIQUE(client_id, transaction_id)
                )
            """
            )

            # Copy data from old table to new table, joining with clients table to get client_id
            cursor.execute(
                """
                INSERT INTO transaction_classifications_new (
                    client_id,
                    transaction_id,
                    payee,
                    payee_confidence,
                    payee_notes,
                    category,
                    base_category,
                    category_confidence,
                    category_notes,
                    expense_type,
                    business_percentage,
                    business_confidence,
                    business_notes,
                    required_documentation,
                    created_at,
                    updated_at
                )
                SELECT 
                    c.id,
                    tc.transaction_id,
                    tc.payee,
                    tc.payee_confidence,
                    tc.payee_notes,
                    tc.category,
                    tc.base_category,
                    tc.category_confidence,
                    tc.category_notes,
                    tc.expense_type,
                    tc.business_percentage,
                    tc.business_confidence,
                    tc.business_notes,
                    tc.required_documentation,
                    tc.created_at,
                    tc.updated_at
                FROM transaction_classifications tc
                JOIN clients c ON tc.client_name = c.name
            """
            )

            # Drop old table
            cursor.execute("DROP TABLE transaction_classifications")

            # Rename new table to original name
            cursor.execute(
                "ALTER TABLE transaction_classifications_new RENAME TO transaction_classifications"
            )

            # Create index on client_id and transaction_id
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_transaction_classifications_client_transaction 
                ON transaction_classifications(client_id, transaction_id)
            """
            )

            logger.info("Successfully migrated transaction_classifications table")

        except Exception as e:
            logger.error(f"Error during migration: {str(e)}")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    migrate_transaction_classifications()
