"""Transaction normalization menu and utilities."""

import os
from typing import Optional
from ..db.client_db import ClientDB


def normalize_transactions_menu(db: ClientDB) -> None:
    """Menu for transaction normalization operations."""
    while True:
        print("\nTransaction Normalization Menu")
        print("1. Normalize All Transactions")
        print("2. View Normalization Status")
        print("3. Back to Main Menu")

        choice = input("\nEnter your choice (1-3): ")

        if choice == "1":
            # Normalize all transactions
            try:
                print("\nNormalizing transactions...")
                # This would need to be implemented based on your normalization logic
                print("Feature not yet implemented.")
            except Exception as e:
                print(f"\nError normalizing transactions: {str(e)}")

        elif choice == "2":
            # View normalization status
            print("\nNormalization Status:")
            print("Feature not yet implemented.")
            # This would show statistics about normalized transactions

        elif choice == "3":
            break

        else:
            print("\nInvalid choice. Please try again.")
