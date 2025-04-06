"""Database manager for client data."""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Optional, List, Any
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
                    industry_keywords JSON,
                    category_patterns JSON,
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

            # Transaction processing status
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transaction_status (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    transaction_id TEXT NOT NULL,
                    -- Status for each pass
                    pass_1_status TEXT CHECK(pass_1_status IN ('pending', 'processing', 'completed', 'error', 'skipped', 'force_required')),
                    pass_1_error TEXT,
                    pass_1_processed_at TIMESTAMP,
                    pass_2_status TEXT CHECK(pass_2_status IN ('pending', 'processing', 'completed', 'error', 'skipped', 'force_required')),
                    pass_2_error TEXT,
                    pass_2_processed_at TIMESTAMP,
                    pass_3_status TEXT CHECK(pass_3_status IN ('pending', 'processing', 'completed', 'error', 'skipped', 'force_required')),
                    pass_3_error TEXT,
                    pass_3_processed_at TIMESTAMP,
                    -- Metadata
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    FOREIGN KEY(client_id, transaction_id) REFERENCES normalized_transactions(client_id, transaction_id),
                    UNIQUE(client_id, transaction_id)
                )
            """
            )

            # Initialize status for new transactions
            conn.execute(
                """
                INSERT INTO transaction_status (client_id, transaction_id, pass_1_status, pass_2_status, pass_3_status)
                SELECT t.client_id, t.transaction_id, 'pending', 'pending', 'pending'
                FROM normalized_transactions t
                LEFT JOIN transaction_status s ON t.client_id = s.client_id AND t.transaction_id = s.transaction_id
                WHERE s.id IS NULL
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

            # Client-specific expense categories
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_expense_categories (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    category_name TEXT NOT NULL,
                    category_type TEXT CHECK(category_type IN ('other_expense', 'custom_category')) NOT NULL,
                    description TEXT,
                    tax_year INTEGER NOT NULL,
                    worksheet TEXT CHECK(worksheet IN ('6A', 'Vehicle', 'HomeOffice')) NOT NULL,
                    parent_category TEXT,  -- Links to standard category if this is a subcategory
                    line_number TEXT,      -- For custom line items in Other Expenses
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    UNIQUE(client_id, category_name, tax_year)
                )
            """
            )

            # Modify transaction_classifications table - add columns one at a time
            for column_def in [
                "base_category TEXT",
                "base_category_confidence TEXT CHECK(base_category_confidence IN ('high', 'medium', 'low'))",
                "worksheet TEXT CHECK(worksheet IN ('6A', 'Vehicle', 'HomeOffice'))",
                "tax_category TEXT",
                "tax_subcategory TEXT",
                "tax_year INTEGER",
                "tax_worksheet_line_number TEXT",
                "split_amount DECIMAL",
                "previous_year_comparison TEXT",
                "is_reviewed BOOLEAN DEFAULT 0",
                "review_notes TEXT",
                "last_reviewed_at TIMESTAMP",
                "expense_type TEXT CHECK(expense_type IN ('business', 'personal', 'mixed'))",
                "business_percentage INTEGER",
                "business_description TEXT",
                "general_category TEXT",
                "business_context TEXT",
            ]:
                try:
                    conn.execute(
                        f"ALTER TABLE transaction_classifications ADD COLUMN {column_def}"
                    )
                except sqlite3.OperationalError as e:
                    # Ignore error if column already exists
                    if "duplicate column name" not in str(e).lower():
                        raise

            # Table for tracking tax worksheet totals
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tax_worksheet_totals (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    tax_year INTEGER NOT NULL,
                    worksheet TEXT NOT NULL,
                    category TEXT NOT NULL,
                    total_amount DECIMAL NOT NULL,
                    previous_year_amount DECIMAL,
                    variance_percentage DECIMAL,
                    variance_notes TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    UNIQUE(client_id, tax_year, worksheet, category)
                )
            """
            )

            # Business rules table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS business_rules (
                    id INTEGER PRIMARY KEY,
                    client_id INTEGER NOT NULL,
                    rule_type TEXT NOT NULL CHECK(rule_type IN ('category', 'payee', 'amount', 'composite')),
                    rule_name TEXT NOT NULL,
                    rule_description TEXT,
                    conditions JSON NOT NULL,  -- Stores rule matching conditions
                    actions JSON NOT NULL,     -- Stores actions to take when rule matches
                    priority INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1,
                    ai_generated BOOLEAN DEFAULT 0,
                    ai_confidence TEXT CHECK(ai_confidence IN ('high', 'medium', 'low')),
                    ai_reasoning TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(client_id) REFERENCES clients(id),
                    UNIQUE(client_id, rule_name)
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
        logger.debug(f"Starting database save for client: {client_name}")
        client_id = self.get_client_id(client_name)
        logger.debug(f"Got client_id: {client_id}")

        # Log the profile data for debugging
        logger.debug(
            f"Saving profile with industry_keywords: {profile.get('industry_keywords', {})}"
        )

        try:
            with sqlite3.connect(self.db_path) as conn:
                logger.debug("Connected to database")
                cursor = conn.execute(
                    """
                    INSERT OR REPLACE INTO business_profiles (
                        client_id,
                        business_type,
                        business_description,
                        custom_categories,
                        industry_keywords,
                        category_patterns,
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
                        json.dumps(profile.get("industry_keywords", {})),
                        json.dumps(profile.get("category_patterns", {})),
                        profile.get("industry_insights"),
                        json.dumps(profile.get("category_hierarchy", {})),
                        profile.get("business_context"),
                        json.dumps(profile),  # Store full profile as backup
                    ),
                )
                logger.debug("Executed INSERT OR REPLACE")

                # Verify the save
                cursor = conn.execute(
                    """
                    SELECT industry_keywords, business_type, business_description
                    FROM business_profiles
                    WHERE client_id = ?
                    """,
                    (client_id,),
                )
                result = cursor.fetchone()
                if result:
                    logger.debug(
                        f"Verified save - found profile with business_type: {result[1]}"
                    )
                    if result[0]:  # industry_keywords
                        saved_keywords = json.loads(result[0])
                        logger.debug(
                            f"Verified saved industry_keywords: {saved_keywords}"
                        )
                    else:
                        logger.warning("No industry_keywords found after save!")
                else:
                    logger.error("Failed to find profile after save!")

                logger.info(f"Saved profile for client {client_name} to database")
        except Exception as e:
            logger.error(f"Database error saving profile: {str(e)}")
            logger.exception("Full traceback:")

    def load_profile(self, client_name: str) -> Optional[Dict]:
        """Load business profile from database."""
        client_id = self.get_client_id(client_name)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    business_type,
                    business_description,
                    custom_categories,
                    industry_keywords,
                    category_patterns,
                    industry_insights,
                    category_hierarchy,
                    business_context,
                    profile_data
                FROM business_profiles 
                WHERE client_id = ?
                """,
                (client_id,),
            )
            result = cursor.fetchone()

            if result:
                # Load the full profile from profile_data
                profile = json.loads(result[8]) if result[8] else {}

                # Update with the latest values from individual columns
                profile.update(
                    {
                        "business_type": result[0],
                        "business_description": result[1],
                        "custom_categories": json.loads(result[2]) if result[2] else [],
                        "industry_keywords": json.loads(result[3]) if result[3] else {},
                        "category_patterns": json.loads(result[4]) if result[4] else {},
                        "industry_insights": result[5],
                        "category_hierarchy": (
                            json.loads(result[6]) if result[6] else {}
                        ),
                        "business_context": result[7],
                    }
                )

                return profile

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
                        c.tax_implications,
                        c.expense_type,
                        c.tax_category,
                        c.tax_subcategory,
                        c.tax_year,
                        c.tax_worksheet_line_number,
                        c.worksheet,
                        c.split_amount,
                        c.previous_year_comparison,
                        c.is_reviewed,
                        c.review_notes,
                        c.last_reviewed_at,
                        c.business_percentage,
                        c.business_description,
                        c.general_category,
                        c.business_context
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
                "last_reviewed_at",
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

    def update_transaction_status(
        self, transaction_id: str, status_data: Dict[str, Any]
    ) -> None:
        """Update transaction status data.

        Args:
            transaction_id: The transaction ID to update
            status_data: Dictionary of status data to update
        """
        try:
            client_id = status_data.get("client_id")
            if not client_id:
                raise ValueError("client_id is required in status_data")

            with sqlite3.connect(self.db_path) as conn:
                # Convert status data to column updates
                updates = []
                values = []
                for key, value in status_data.items():
                    updates.append(f"{key} = ?")
                    values.append(value)

                # Add updated_at timestamp
                updates.append("updated_at = CURRENT_TIMESTAMP")

                # Build and execute update query
                query = f"""
                    UPDATE transaction_status 
                    SET {', '.join(updates)}
                    WHERE client_id = ? AND transaction_id = ?
                """
                values.extend([client_id, transaction_id])

                conn.execute(query, values)

                # If no row was updated, we need to insert
                if conn.total_changes == 0:
                    # Initialize status fields if not provided
                    for pass_num in range(1, 4):
                        if f"pass_{pass_num}_status" not in status_data:
                            status_data[f"pass_{pass_num}_status"] = "pending"
                            status_data[f"pass_{pass_num}_error"] = None
                            status_data[f"pass_{pass_num}_processed_at"] = None

                    # Prepare columns and values for insert
                    columns = list(status_data.keys()) + ["transaction_id"]
                    placeholders = ["?"] * len(columns)
                    values = list(status_data.values()) + [transaction_id]

                    # Build and execute insert query
                    query = f"""
                        INSERT INTO transaction_status 
                        ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    conn.execute(query, values)

        except sqlite3.Error as e:
            logger.error(f"Database error updating transaction status: {str(e)}")
            raise

    def get_transaction_status(
        self, client_name: str, transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get status of a transaction.

        Args:
            client_name: Name of the client
            transaction_id: ID of the transaction

        Returns:
            Dictionary containing status information for each pass, or None if not found
        """
        try:
            client_id = self.get_client_id(client_name)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT 
                        pass_1_status, pass_1_error, pass_1_processed_at,
                        pass_2_status, pass_2_error, pass_2_processed_at,
                        pass_3_status, pass_3_error, pass_3_processed_at
                    FROM transaction_status
                    WHERE client_id = ? AND transaction_id = ?
                    """,
                    (client_id, transaction_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                return {
                    "pass_1": {
                        "status": row[0],
                        "error": row[1],
                        "processed_at": row[2],
                    },
                    "pass_2": {
                        "status": row[3],
                        "error": row[4],
                        "processed_at": row[5],
                    },
                    "pass_3": {
                        "status": row[6],
                        "error": row[7],
                        "processed_at": row[8],
                    },
                }
        except Exception as e:
            logger.error(f"Error getting transaction status: {e}")
            return None

    def add_client_category(
        self,
        client_name: str,
        category_name: str,
        category_type: str,
        description: str,
        tax_year: int,
        worksheet: str = "6A",
        parent_category: Optional[str] = None,
        line_number: Optional[str] = None,
    ) -> None:
        """Add a new client-specific expense category."""
        client_id = self.get_client_id(client_name)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO client_expense_categories (
                    client_id,
                    category_name,
                    category_type,
                    description,
                    tax_year,
                    worksheet,
                    parent_category,
                    line_number,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT (client_id, category_name, tax_year)
                DO UPDATE SET
                    category_type = excluded.category_type,
                    description = excluded.description,
                    worksheet = excluded.worksheet,
                    parent_category = excluded.parent_category,
                    line_number = excluded.line_number,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    client_id,
                    category_name,
                    category_type,
                    description,
                    tax_year,
                    worksheet,
                    parent_category,
                    line_number,
                ),
            )

    def get_client_categories(
        self,
        client_name: str,
        tax_year: Optional[int] = None,
        include_inactive: bool = False,
    ) -> List[Dict]:
        """Get all categories for a client, optionally filtered by tax year."""
        client_id = self.get_client_id(client_name)

        query = """
            SELECT 
                category_name,
                category_type,
                description,
                tax_year,
                worksheet,
                parent_category,
                line_number,
                is_active,
                created_at,
                updated_at
            FROM client_expense_categories
            WHERE client_id = ?
        """
        params = [client_id]

        if tax_year:
            query += " AND tax_year = ?"
            params.append(tax_year)

        if not include_inactive:
            query += " AND is_active = 1"

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def deactivate_client_category(
        self, client_name: str, category_name: str, tax_year: int
    ) -> None:
        """Deactivate a client category instead of deleting it."""
        client_id = self.get_client_id(client_name)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE client_expense_categories
                SET is_active = 0,
                    updated_at = CURRENT_TIMESTAMP
                WHERE client_id = ?
                AND category_name = ?
                AND tax_year = ?
                """,
                (client_id, category_name, tax_year),
            )

    def create_transaction_status_table(self):
        """Create the transaction_status table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS transaction_status (
                    transaction_id TEXT PRIMARY KEY,
                    pass_1_complete BOOLEAN DEFAULT 0,
                    pass_1_error TEXT,
                    pass_1_completed_at TIMESTAMP,
                    pass_2_complete BOOLEAN DEFAULT 0,
                    pass_2_error TEXT,
                    pass_2_completed_at TIMESTAMP,
                    pass_3_complete BOOLEAN DEFAULT 0,
                    pass_3_error TEXT,
                    pass_3_completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (transaction_id) REFERENCES normalized_transactions(transaction_id)
                )
            """
            )
            conn.commit()

    def get_transactions_by_status(
        self, pass_number: int, complete: bool = True, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get transactions based on their processing status for a specific pass."""
        query = f"""
            SELECT t.*, s.*
            FROM normalized_transactions t
            LEFT JOIN transaction_status s ON t.transaction_id = s.transaction_id
            WHERE s.pass_{pass_number}_complete = ?
        """
        if limit:
            query += f" LIMIT {limit}"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, (1 if complete else 0,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_processing_summary(self) -> Dict[str, Any]:
        """Get a summary of transaction processing status."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_transactions,
                    SUM(CASE WHEN s.pass_1_complete = 1 THEN 1 ELSE 0 END) as pass_1_complete,
                    SUM(CASE WHEN s.pass_2_complete = 1 THEN 1 ELSE 0 END) as pass_2_complete,
                    SUM(CASE WHEN s.pass_3_complete = 1 THEN 1 ELSE 0 END) as pass_3_complete,
                    SUM(CASE WHEN s.pass_1_error IS NOT NULL THEN 1 ELSE 0 END) as pass_1_errors,
                    SUM(CASE WHEN s.pass_2_error IS NOT NULL THEN 1 ELSE 0 END) as pass_2_errors,
                    SUM(CASE WHEN s.pass_3_error IS NOT NULL THEN 1 ELSE 0 END) as pass_3_errors
                FROM normalized_transactions t
                LEFT JOIN transaction_status s ON t.transaction_id = s.transaction_id
            """
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def reset_transaction_status(
        self, client_name: str, transaction_id: str, pass_number: Optional[int] = None
    ) -> None:
        """Reset transaction status to pending."""
        try:
            client_id = self.get_client_id(client_name)
            with sqlite3.connect(self.db_path) as conn:
                if pass_number:
                    # Reset specific pass
                    conn.execute(
                        f"""
                        UPDATE transaction_status 
                        SET 
                            pass_{pass_number}_status = 'pending',
                            pass_{pass_number}_error = NULL,
                            pass_{pass_number}_processed_at = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE client_id = ? AND transaction_id = ?
                        """,
                        (client_id, transaction_id),
                    )
                else:
                    # Reset all passes
                    conn.execute(
                        """
                        UPDATE transaction_status 
                        SET 
                            pass_1_status = 'pending',
                            pass_1_error = NULL,
                            pass_1_processed_at = NULL,
                            pass_2_status = 'pending',
                            pass_2_error = NULL,
                            pass_2_processed_at = NULL,
                            pass_3_status = 'pending',
                            pass_3_error = NULL,
                            pass_3_processed_at = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE client_id = ? AND transaction_id = ?
                        """,
                        (client_id, transaction_id),
                    )
        except Exception as e:
            logger.error(f"Error resetting transaction status: {e}")
            raise

    def update_transaction_classification(
        self, transaction_id: str, classification_data: Dict[str, Any]
    ) -> None:
        """Update transaction classification data.

        Args:
            transaction_id: The transaction ID to update
            classification_data: Dictionary of classification data to update
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys = ON")

                # First check if the row exists
                check_query = """
                    SELECT * FROM transaction_classifications
                    WHERE transaction_id = ?
                """
                cursor = conn.execute(check_query, (transaction_id,))
                existing_row = cursor.fetchone()

                if existing_row:
                    # Get column names
                    column_names = [
                        description[0] for description in cursor.description
                    ]
                    existing_data = dict(zip(column_names, existing_row))
                    logger.info(f"Existing data for transaction {transaction_id}:")
                    for key, value in existing_data.items():
                        logger.info(f"  • {key}: {value}")

                    # Build update query
                    updates = []
                    values = []
                    for key, value in classification_data.items():
                        if key not in ["id", "created_at", "transaction_id"]:
                            updates.append(f"{key} = ?")
                            values.append(value)

                    query = f"""
                        UPDATE transaction_classifications 
                        SET {', '.join(updates)}
                        WHERE transaction_id = ?
                    """
                    values.append(transaction_id)

                    # Log the query and values
                    logger.info(f"Executing UPDATE for transaction {transaction_id}")
                    logger.info(f"Query: {query}")
                    logger.info(f"Values: {values}")

                    # Execute update
                    conn.execute(query, values)
                    logger.info(f"Rows affected by UPDATE: {conn.total_changes}")
                else:
                    # Prepare insert
                    columns = list(classification_data.keys()) + ["transaction_id"]
                    placeholders = ["?"] * len(columns)
                    values = list(classification_data.values()) + [transaction_id]

                    query = f"""
                        INSERT INTO transaction_classifications 
                        ({', '.join(columns)})
                        VALUES ({', '.join(placeholders)})
                    """
                    # Log the query and values
                    logger.info(f"Executing INSERT for transaction {transaction_id}")
                    logger.info(f"Query: {query}")
                    logger.info(f"Values: {values}")

                    # Execute insert
                    conn.execute(query, values)
                    logger.info(f"Rows affected by INSERT: {conn.total_changes}")

                # Verify the update
                verify_query = """
                    SELECT * FROM transaction_classifications
                    WHERE transaction_id = ?
                """
                cursor = conn.execute(verify_query, (transaction_id,))
                result = cursor.fetchone()
                if result:
                    column_names = [
                        description[0] for description in cursor.description
                    ]
                    logger.info(
                        f"Verification result for transaction {transaction_id}:"
                    )
                    for i, value in enumerate(result):
                        logger.info(f"  • {column_names[i]}: {value}")
                else:
                    logger.warning(
                        f"No row found after update for transaction {transaction_id}!"
                    )

        except sqlite3.Error as e:
            logger.error(
                f"Database error updating transaction classification: {str(e)}"
            )
            raise

    def get_transaction_classification(
        self, transaction_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get classification data for a transaction.

        Args:
            transaction_id: The transaction ID to get classification for

        Returns:
            Dictionary of classification data or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT *
                    FROM transaction_classifications
                    WHERE transaction_id = ?
                    """,
                    (transaction_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

        except sqlite3.Error as e:
            logger.error(f"Database error getting transaction classification: {str(e)}")
            raise

    def get_all_categories(self, client_name: str) -> List[str]:
        """Get all unique categories used in transactions."""
        client_id = self.get_client_id(client_name)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT base_category 
                FROM transaction_classifications 
                WHERE client_id = ? 
                AND base_category IS NOT NULL
                """,
                (client_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def get_all_payees(self, client_name: str) -> List[str]:
        """Get all unique payees in transactions."""
        client_id = self.get_client_id(client_name)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT payee 
                FROM transaction_classifications 
                WHERE client_id = ? 
                AND payee IS NOT NULL 
                AND payee != 'Unknown Payee'
                """,
                (client_id,),
            )
            return [row[0] for row in cursor.fetchall()]

    def load_transactions_by_category(
        self, client_name: str, category: str
    ) -> List[Dict]:
        """Load all transactions for a given category."""
        client_id = self.get_client_id(client_name)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    t.transaction_id,
                    t.transaction_date,
                    t.amount,
                    t.description,
                    c.payee,
                    c.base_category,
                    c.business_percentage,
                    c.is_reviewed
                FROM normalized_transactions t
                JOIN transaction_classifications c 
                    ON t.transaction_id = c.transaction_id 
                    AND t.client_id = c.client_id
                WHERE t.client_id = ? 
                AND c.base_category = ?
                ORDER BY t.transaction_date DESC
                """,
                (client_id, category),
            )
            return [dict(row) for row in cursor.fetchall()]

    def load_transactions_by_business_percentage(
        self, client_name: str, percentage: int
    ) -> List[Dict]:
        """Load all transactions with a specific business percentage."""
        client_id = self.get_client_id(client_name)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    t.transaction_id,
                    t.transaction_date,
                    t.amount,
                    t.description,
                    c.payee,
                    c.base_category,
                    c.business_percentage,
                    c.is_reviewed
                FROM normalized_transactions t
                JOIN transaction_classifications c 
                    ON t.transaction_id = c.transaction_id 
                    AND t.client_id = c.client_id
                WHERE t.client_id = ? 
                AND c.business_percentage = ?
                ORDER BY t.transaction_date DESC
                """,
                (client_id, percentage),
            )
            return [dict(row) for row in cursor.fetchall()]

    def load_transactions_by_payee(self, client_name: str, payee: str) -> List[Dict]:
        """Load all transactions for a given payee."""
        client_id = self.get_client_id(client_name)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    t.transaction_id,
                    t.transaction_date,
                    t.amount,
                    t.description,
                    c.payee,
                    c.base_category,
                    c.business_percentage,
                    c.is_reviewed
                FROM normalized_transactions t
                JOIN transaction_classifications c 
                    ON t.transaction_id = c.transaction_id 
                    AND t.client_id = c.client_id
                WHERE t.client_id = ? 
                AND c.payee = ?
                ORDER BY t.transaction_date DESC
                """,
                (client_id, payee),
            )
            return [dict(row) for row in cursor.fetchall()]

    def load_transactions_by_ids(
        self, client_name: str, transaction_ids: List[str]
    ) -> List[Dict]:
        """Load specific transactions by their IDs."""
        client_id = self.get_client_id(client_name)
        placeholders = ",".join("?" * len(transaction_ids))
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"""
                SELECT 
                    t.transaction_id,
                    t.transaction_date,
                    t.amount,
                    t.description,
                    c.payee,
                    c.base_category,
                    c.business_percentage,
                    c.is_reviewed
                FROM normalized_transactions t
                JOIN transaction_classifications c 
                    ON t.transaction_id = c.transaction_id 
                    AND t.client_id = c.client_id
                WHERE t.client_id = ? 
                AND t.transaction_id IN ({placeholders})
                ORDER BY t.transaction_date DESC
                """,
                (client_id, *transaction_ids),
            )
            return [dict(row) for row in cursor.fetchall()]

    def batch_update_business_percentage(
        self, client_name: str, transaction_ids: List[str], percentage: int
    ) -> None:
        """Update business percentage for multiple transactions."""
        client_id = self.get_client_id(client_name)
        placeholders = ",".join("?" * len(transaction_ids))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"""
                UPDATE transaction_classifications
                SET 
                    business_percentage = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE client_id = ? 
                AND transaction_id IN ({placeholders})
                """,
                (percentage, client_id, *transaction_ids),
            )
            conn.commit()

    def batch_update_review_status(
        self,
        client_name: str,
        transaction_ids: List[str],
        is_reviewed: bool,
        review_notes: Optional[str] = None,
    ) -> None:
        """Update review status for multiple transactions."""
        client_id = self.get_client_id(client_name)
        placeholders = ",".join("?" * len(transaction_ids))
        with sqlite3.connect(self.db_path) as conn:
            if review_notes:
                conn.execute(
                    f"""
                    UPDATE transaction_classifications
                    SET 
                        is_reviewed = ?,
                        review_notes = ?,
                        last_reviewed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE client_id = ? 
                    AND transaction_id IN ({placeholders})
                    """,
                    (is_reviewed, review_notes, client_id, *transaction_ids),
                )
            else:
                conn.execute(
                    f"""
                    UPDATE transaction_classifications
                    SET 
                        is_reviewed = ?,
                        last_reviewed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE client_id = ? 
                    AND transaction_id IN ({placeholders})
                    """,
                    (is_reviewed, client_id, *transaction_ids),
                )
            conn.commit()
