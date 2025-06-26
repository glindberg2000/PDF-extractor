#!/usr/bin/env python3
import os
from dataextractai.menu import start_menu
from typing import Optional
import pandas as pd
from dataextractai.agents.transaction_classifier import TransactionClassifier


def display_banner():
    """Display the Amelia AI Bookkeeping banner."""
    banner = r"""
╔══════════════════════════════════════════════════════════════════════════╗
║      █████╗ ███╗   ███╗███████╗██╗     ██╗ █████╗    █████╗ ██╗          ║
║     ██╔══██╗████╗ ████║██╔════╝██║     ██║██╔══██╗  ██╔══██╗██║          ║
║     ███████║██╔████╔██║█████╗  ██║     ██║███████║  ███████║██║          ║
║     ██╔══██║██║╚██╔╝██║██╔══╝  ██║     ██║██╔══██║  ██╔══██║██║          ║
║     ██║  ██║██║ ╚═╝ ██║███████╗███████╗██║██║  ██║  ██║  ██║██║          ║
║     ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝╚═╝╚═╝  ╚═╝  ╚═╝  ╚═╝╚═╝          ║
╠══════════════════════════════════════════════════════════════════════════╣
║                 🤖  AMELIA AI  -  LLM-POWERED BOOKKEEPING  🤖            ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)
    print("=" * 80)  # Separator line


def process_transactions(
    client_name: str,
    model_type: str = "fast",
    start_row: Optional[int] = None,
    end_row: Optional[int] = None,
    resume_from_pass: Optional[int] = None,
):
    """Process transactions for a client."""
    try:
        # Load transactions
        transactions_file = os.path.join(
            "data", "transactions", f"{client_name}_transactions.csv"
        )
        if not os.path.exists(transactions_file):
            print(f"Error: Transactions file not found: {transactions_file}")
            return

        transactions_df = pd.read_csv(transactions_file)
        if transactions_df.empty:
            print("Error: No transactions found in the file")
            return

        # Initialize classifier
        classifier = TransactionClassifier(client_name, model_type)

        # Process transactions
        print(f"\nProcessing transactions for {client_name}...")
        if start_row is not None or end_row is not None:
            print(
                f"Processing rows {start_row if start_row is not None else 0} to {end_row if end_row is not None else len(transactions_df)}"
            )
        if resume_from_pass is not None:
            print(f"Resuming from pass {resume_from_pass}")

        classified_df = classifier.classify_transactions(
            transactions_df,
            start_row=start_row,
            end_row=end_row,
            resume_from_pass=resume_from_pass,
        )

        print("\nTransaction processing completed successfully!")

    except Exception as e:
        print(f"Error processing transactions: {str(e)}")
        raise


def main():
    """Main entry point."""
    # Display startup banner
    display_banner()

    # Ensure required directories exist
    required_dirs = ["data/transactions", "data/profiles", "logs"]
    for dir_path in required_dirs:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            print(f"Created directory: {dir_path}")

    # Start the interactive menu
    start_menu()


if __name__ == "__main__":
    main()
