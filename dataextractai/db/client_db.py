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

            # Normalized transactions table
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
        """Save normalized transactions to database."""
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
            # First, delete existing transactions for this client
            conn.execute(
                "DELETE FROM normalized_transactions WHERE client_id = ?", (client_id,)
            )

            # Insert new transactions
            for _, row in df_copy.iterrows():
                conn.execute(
                    """
                    INSERT INTO normalized_transactions (
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
                        account_number
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

            logger.info(
                f"Saved {len(df_copy)} normalized transactions for client {client_name}"
            )

    def load_normalized_transactions(self, client_name: str) -> pd.DataFrame:
        """Load normalized transactions from database."""
        client_id = self.get_client_id(client_name)

        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT 
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
                    account_number
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
