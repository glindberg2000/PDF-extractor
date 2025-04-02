"""Database manager for client data."""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Optional, List
import logging
import os
import pandas as pd

logger = logging.getLogger(__name__)


class ClientDB:
    """Database manager for client data."""

    def __init__(self):
        """Initialize database connection."""
        self.db_path = os.path.join("data", "db", "clients.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Clients table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Business profiles table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS business_profiles (
                    client_id INTEGER PRIMARY KEY,
                    business_type TEXT,
                    business_description TEXT,
                    custom_categories JSON,
                    ai_generated_categories JSON,
                    common_patterns JSON,
                    industry_insights TEXT,
                    category_hierarchy JSON,
                    business_context TEXT,
                    profile_data JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id)
                )
            """
            )

            # Normalized transactions table (core transaction data only)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS normalized_transactions (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    transaction_id TEXT NOT NULL,
                    transaction_date DATE NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    normalized_amount REAL,
                    source TEXT NOT NULL,
                    transaction_type TEXT,
                    file_path TEXT,
                    statement_start_date DATE,
                    statement_end_date DATE,
                    account_number TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    UNIQUE(client_id, transaction_id)
                )
            """
            )

            # Transaction classifications table (all classification data)
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transaction_classifications (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    transaction_id TEXT NOT NULL,
                    -- Payee identification (first pass)
                    payee TEXT,
                    payee_confidence TEXT CHECK(payee_confidence IN ('high', 'medium', 'low')),
                    payee_reasoning TEXT,
                    -- Category assignment (second pass)
                    category TEXT,
                    category_confidence TEXT CHECK(category_confidence IN ('high', 'medium', 'low')),
                    category_reasoning TEXT,
                    suggested_new_category TEXT,
                    new_category_reasoning TEXT,
                    -- Business/Personal classification (third pass)
                    classification TEXT CHECK(classification IN ('Business', 'Personal', 'Unclassified')),
                    classification_confidence TEXT CHECK(classification_confidence IN ('high', 'medium', 'low')),
                    classification_reasoning TEXT,
                    tax_implications TEXT,
                    -- Metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    FOREIGN KEY(client_id, transaction_id) REFERENCES normalized_transactions(client_id, transaction_id),
                    UNIQUE(client_id, transaction_id)
                )
            """
            )

            # Transaction classification cache
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transaction_cache (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    cache_key TEXT NOT NULL,
                    pass_type TEXT NOT NULL CHECK(pass_type IN ('payee', 'category', 'classification')),
                    result JSON NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    UNIQUE(client_id, cache_key, pass_type)
                )
            """
            )

    def get_client_id(self, client_name: str) -> Optional[int]:
        """Get client ID from name, creating if doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Try to get existing client
            cursor = conn.execute(
                "SELECT id FROM clients WHERE name = ?", (client_name,)
            )
            result = cursor.fetchone()

            if result:
                return result[0]

            # Create new client
            cursor = conn.execute(
                """
                INSERT INTO clients (name, created_at, updated_at)
                VALUES (?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                (client_name,),
            )
            return cursor.lastrowid

    def save_profile(self, client_name: str, profile: Dict) -> None:
        """Save business profile to database."""
        client_id = self.get_client_id(client_name)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO business_profiles (
                    client_id,
                    business_type,
                    business_description,
                    custom_categories,
                    ai_generated_categories,
                    common_patterns,
                    industry_insights,
                    category_hierarchy,
                    business_context,
                    profile_data,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    client_id,
                    profile.get("business_type"),
                    profile.get("business_description"),
                    json.dumps(profile.get("custom_categories", [])),
                    json.dumps(profile.get("ai_generated_categories", [])),
                    json.dumps(profile.get("common_patterns", [])),
                    profile.get("industry_insights"),
                    json.dumps(profile.get("category_hierarchy", {})),
                    profile.get("business_context"),
                    json.dumps(profile),  # Store full profile as backup
                ),
            )
            logger.info(f"Saved profile for client {client_name} to database")

    def load_profile(self, client_name: str) -> Optional[Dict]:
        """Load business profile from database."""
        client_id = self.get_client_id(client_name)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT profile_data FROM business_profiles WHERE client_id = ?",
                (client_id,),
            )
            result = cursor.fetchone()

            if result and result[0]:
                return json.loads(result[0])
            return None

    def save_normalized_transactions(
        self, client_name: str, transactions_df: pd.DataFrame
    ) -> None:
        """Save normalized transactions to database, preserving any existing classifications."""
        client_id = self.get_client_id(client_name)

        # Ensure required columns exist
        required_columns = [
            "transaction_id",
            "transaction_date",
            "description",
            "amount",
            "source",
        ]
        missing_columns = [
            col for col in required_columns if col not in transactions_df.columns
        ]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Convert dates to ISO format strings
        date_columns = [
            "transaction_date",
            "statement_start_date",
            "statement_end_date",
        ]
        df_copy = transactions_df.copy()
        for col in date_columns:
            if col in df_copy.columns:
                df_copy[col] = pd.to_datetime(
                    df_copy[col], errors="coerce"
                ).dt.strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            # First, delete any transactions that no longer exist in the new data
            existing_transaction_ids = tuple(df_copy["transaction_id"].astype(str))
            if existing_transaction_ids:
                conn.execute(
                    """
                    DELETE FROM normalized_transactions 
                    WHERE client_id = ? 
                    AND transaction_id NOT IN ({})
                    """.format(
                        ",".join("?" * len(existing_transaction_ids))
                    ),
                    (client_id, *existing_transaction_ids),
                )

            # Insert or update transactions
            for _, row in df_copy.iterrows():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO normalized_transactions (
                        client_id,
                        transaction_id,
                        transaction_date,
                        description,
                        amount,
                        normalized_amount,
                        source,
                        transaction_type,
                        file_path,
                        statement_start_date,
                        statement_end_date,
                        account_number,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        client_id,
                        str(row["transaction_id"]),
                        row["transaction_date"],
                        row["description"],
                        float(row["amount"]),
                        float(row.get("normalized_amount", row["amount"])),
                        row["source"],
                        row.get("transaction_type"),
                        row.get("file_path"),
                        row.get("statement_start_date"),
                        row.get("statement_end_date"),
                        row.get("account_number"),
                    ),
                )

            # Clean up orphaned classifications
            conn.execute(
                """
                DELETE FROM transaction_classifications
                WHERE client_id = ?
                AND transaction_id NOT IN (
                    SELECT transaction_id 
                    FROM normalized_transactions 
                    WHERE client_id = ?
                )
                """,
                (client_id, client_id),
            )

            logger.info(
                f"Saved {len(df_copy)} normalized transactions for client {client_name}"
            )

    def load_normalized_transactions(
        self, client_name: str, include_classifications: bool = True
    ) -> pd.DataFrame:
        """Load normalized transactions from database with optional classification data."""
        client_id = self.get_client_id(client_name)

        with sqlite3.connect(self.db_path) as conn:
            if include_classifications:
                query = """
                    SELECT 
                        t.*,
                        c.payee,
                        c.payee_confidence,
                        c.payee_reasoning,
                        c.category,
                        c.category_confidence,
                        c.category_reasoning,
                        c.suggested_new_category,
                        c.new_category_reasoning,
                        c.classification,
                        c.classification_confidence,
                        c.classification_reasoning,
                        c.tax_implications
                    FROM normalized_transactions t
                    LEFT JOIN transaction_classifications c 
                        ON t.client_id = c.client_id 
                        AND t.transaction_id = c.transaction_id
                    WHERE t.client_id = ?
                    ORDER BY t.transaction_date
                """
            else:
                query = """
                    SELECT *
                    FROM normalized_transactions
                    WHERE client_id = ?
                    ORDER BY transaction_date
                """

            df = pd.read_sql_query(query, conn, params=(client_id,))

            # Convert date strings back to datetime
            date_columns = [
                "transaction_date",
                "statement_start_date",
                "statement_end_date",
            ]
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors="coerce")

            return df

    def _upsert(
        self,
        table: str,
        data: Dict[str, any],
        unique_columns: List[str],
        exclude_from_update: Optional[List[str]] = None,
    ) -> None:
        """Generic upsert function for SQLite.

        Args:
            table: Table name
            data: Dictionary of column names and values
            unique_columns: List of columns that form the unique constraint
            exclude_from_update: Optional list of columns to exclude from UPDATE clause
        """
        if not exclude_from_update:
            exclude_from_update = []

        # Split columns into those for insert and update
        insert_cols = list(data.keys())
        update_cols = [col for col in insert_cols if col not in exclude_from_update]

        # Build the SQL statement
        sql = f"""
            INSERT INTO {table} (
                {", ".join(insert_cols)}
            ) VALUES (
                {", ".join("?" * len(insert_cols))}
            )
            ON CONFLICT ({", ".join(unique_columns)}) DO UPDATE SET
                {", ".join(f"{col} = excluded.{col}" for col in update_cols)}
        """

        # Execute the statement
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(sql, list(data.values()))

    def save_transaction_classification(
        self,
        client_name: str,
        transaction_id: str,
        classification_data: Dict,
        pass_type: str,
    ) -> None:
        """Save classification data for a single transaction."""
        client_id = self.get_client_id(client_name)
        valid_pass_types = {"payee", "category", "classification"}

        if pass_type not in valid_pass_types:
            raise ValueError(f"Invalid pass_type. Must be one of: {valid_pass_types}")

        # First ensure the transaction exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM normalized_transactions
                WHERE client_id = ? AND transaction_id = ?
                """,
                (client_id, transaction_id),
            )
            if not cursor.fetchone():
                raise ValueError(f"Transaction {transaction_id} not found")

        # Map of pass types to their corresponding columns
        pass_columns = {
            "payee": ["payee", "payee_confidence", "payee_reasoning"],
            "category": [
                "category",
                "category_confidence",
                "category_reasoning",
                "suggested_new_category",
                "new_category_reasoning",
            ],
            "classification": [
                "classification",
                "classification_confidence",
                "classification_reasoning",
                "tax_implications",
            ],
        }

        # Prepare data for upsert
        data = {
            "client_id": client_id,
            "transaction_id": transaction_id,
        }

        # Add the classification data for this pass
        for col in pass_columns[pass_type]:
            data[col] = classification_data.get(col)

        # Add NULL values for columns from other passes if this is a new record
        for other_pass, cols in pass_columns.items():
            if other_pass != pass_type:
                for col in cols:
                    if col not in data:
                        data[col] = None

        # Use the generic upsert function
        self._upsert(
            table="transaction_classifications",
            data=data,
            unique_columns=["client_id", "transaction_id"],
            exclude_from_update=["created_at"],  # Don't update creation timestamp
        )

        logger.info(
            f"Saved {pass_type} classification for transaction {transaction_id}"
        )
