import pandas as pd
import logging
from dataextractai.agents.transaction_classifier import TransactionClassifier

# Set up logging
logging.basicConfig(level=logging.INFO)


def test_specific_rows():
    # Initialize the classifier
    classifier = TransactionClassifier("Gene")

    # Load transactions from database
    # Using slightly modified description to force LLM classification
    test_data = {
        "transaction_id": [1226, 1227],
        "description": [
            "SPEEDWAY #44824 - LOS RANCHOS NM",  # Modified format to avoid exact match
            "SPEEDWAY GAS STATION LOS RANCHOS",  # Different format to force LLM
        ],
        "amount": [45.67, 52.89],
        "transaction_date": pd.to_datetime(["2024-04-08", "2024-04-09"]),
    }
    df = pd.DataFrame(test_data)

    # Process the transactions with force processing
    stats = classifier.process_transactions(
        df,
        resume_from_pass=1,
        force_process=True,  # Force LLM processing
        start_row=0,
        end_row=2,
    )

    print("\nProcessing complete!")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    test_specific_rows()
