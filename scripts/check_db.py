"""Check database contents."""

import sqlite3
import json


def check_db():
    """Print database contents."""
    db_path = "data/db/clients.db"

    with sqlite3.connect(db_path) as conn:
        # Check clients table
        print("\nClients:")
        print("-" * 50)
        cursor = conn.execute("SELECT * FROM clients")
        for row in cursor:
            print(f"ID: {row[0]}, Name: {row[1]}, Created: {row[2]}, Updated: {row[3]}")

        # Check profiles
        print("\nBusiness Profiles:")
        print("-" * 50)
        cursor = conn.execute(
            """
            SELECT c.name, bp.business_type, bp.business_description, bp.custom_categories
            FROM clients c
            JOIN business_profiles bp ON c.id = bp.client_id
        """
        )
        for row in cursor:
            print(f"\nClient: {row[0]}")
            print(f"Business Type: {row[1]}")
            print(f"Description: {row[2]}")
            categories = json.loads(row[3]) if row[3] else []
            print(f"Custom Categories: {', '.join(categories)}")


if __name__ == "__main__":
    check_db()
