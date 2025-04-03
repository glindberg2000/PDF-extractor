"""PDF parsing menu and utilities."""

import os
from typing import Optional
from ..db.client_db import ClientDB
from .run_parsers import run_all_parsers


def parse_pdf_menu(db: ClientDB) -> None:
    """Menu for PDF parsing operations."""
    while True:
        print("\nPDF Parsing Menu")
        print("1. Parse All PDF Statements")
        print("2. Parse Specific Statement")
        print("3. View Parsing Status")
        print("4. Back to Main Menu")

        choice = input("\nEnter your choice (1-4): ")

        if choice == "1":
            # Parse all PDFs
            try:
                run_all_parsers()
                print("\nSuccessfully parsed all PDF statements.")
            except Exception as e:
                print(f"\nError parsing PDFs: {str(e)}")

        elif choice == "2":
            # Parse specific statement
            print("\nAvailable statement types:")
            print("1. Wells Fargo Bank")
            print("2. Wells Fargo Credit Card")
            print("3. Chase Credit Card")
            print("4. Bank of America Bank")
            print("5. Bank of America Credit Card")
            print("6. First Republic Bank")

            statement_choice = input("\nEnter statement type (1-6): ")
            pdf_path = input("Enter path to PDF file: ")

            if not os.path.exists(pdf_path):
                print("\nError: File not found.")
                continue

            try:
                # Call appropriate parser based on choice
                # This would need to be implemented based on your parser implementations
                print("\nParsing statement...")
                print("Feature not yet implemented.")
            except Exception as e:
                print(f"\nError parsing statement: {str(e)}")

        elif choice == "3":
            # View parsing status
            print("\nParsing Status:")
            print("Feature not yet implemented.")
            # This would show statistics about parsed files, success rates, etc.

        elif choice == "4":
            break

        else:
            print("\nInvalid choice. Please try again.")
