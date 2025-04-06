#!/usr/bin/env python3
"""Migrate business profiles to use client_id instead of client_name."""

import sqlite3
import os
from pathlib import Path


def migrate_business_profiles():
    """Migrate business profiles to use client_id."""
    db_path = "data/db/clients.db"
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # First, check if we need to migrate
        cursor.execute("PRAGMA table_info(business_profiles)")
        columns = [col[1] for col in cursor.fetchall()]

        if "client_name" not in columns:
            print("No migration needed - table already using client_id")
            return

        # Create temporary table with new schema
        cursor.execute(
            """
            CREATE TABLE business_profiles_new (
                id INTEGER PRIMARY KEY,
                client_id INTEGER NOT NULL UNIQUE,
                profile_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            )
        """
        )

        # Migrate data
        cursor.execute(
            """
            INSERT INTO business_profiles_new (client_id, profile_data, created_at, updated_at)
            SELECT c.id, bp.profile_data, bp.created_at, bp.updated_at
            FROM business_profiles bp
            JOIN clients c ON bp.client_name = c.name
        """
        )

        # Drop old table and rename new one
        cursor.execute("DROP TABLE business_profiles")
        cursor.execute("ALTER TABLE business_profiles_new RENAME TO business_profiles")

        print("Successfully migrated business profiles to use client_id")


if __name__ == "__main__":
    migrate_business_profiles()
