#!/usr/bin/env python3
"""Test script for transaction classification with sample data."""

import pandas as pd
from dataextractai.agents.transaction_classifier import TransactionClassifier
import logging
from colorama import init, Fore, Style

# Initialize colorama
init(autoreset=True)


def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Client name
    CLIENT_NAME = "Gene"  # Replace with actual client name

    # Load transactions
    print(f"{Fore.CYAN}Loading transactions...{Style.RESET_ALL}")
    transactions_df = pd.read_csv("data/output/consolidated_batched.csv")
    print(f"Loaded {len(transactions_df)} transactions")

    # Initialize classifier
    classifier = TransactionClassifier(CLIENT_NAME)

    # Define test parameters
    test_params = {
        "sample_size": 10,  # Number of transactions to test
        "include_keywords": [
            "advertising",  # Include advertising-related transactions
            "expense",  # Include transactions with "expense" in description
            "staging",  # Include staging-related transactions
            "dues",  # Include transactions with dues
        ],
        "force_process": True,  # Force reprocessing of transactions
    }

    print(f"\n{Fore.GREEN}Running test sample with parameters:{Style.RESET_ALL}")
    for key, value in test_params.items():
        print(f"• {key}: {value}")

    # Run test sample
    sample_df, stats = classifier.run_test_sample(transactions_df, **test_params)

    # Save test results
    output_path = "data/output/test_results.xlsx"
    print(f"\n{Fore.GREEN}Saving test results to {output_path}{Style.RESET_ALL}")

    # Create Excel writer
    with pd.ExcelWriter(output_path) as writer:
        # Write transactions
        sample_df.to_excel(writer, sheet_name="Transactions", index=False)

        # Write statistics
        stats_df = pd.DataFrame([stats])
        stats_df.to_excel(writer, sheet_name="Statistics", index=False)

    print(
        f"\n{Fore.GREEN}Test complete! Results saved to {output_path}{Style.RESET_ALL}"
    )


if __name__ == "__main__":
    main()
