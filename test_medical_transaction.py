import pandas as pd
import logging
import json
from dataextractai.agents.transaction_classifier import TransactionClassifier

# Set up logging
logging.basicConfig(level=logging.INFO)


def test_medical_transaction():
    """Test the transaction classifier with a sample medical transaction."""

    # Initialize the classifier
    # If this fails due to client name, you may need to adjust it to a valid client name
    classifier = TransactionClassifier("Gene")

    # Create test transaction data
    test_data = {
        "transaction_id": ["TEST001"],
        "description": ["Medical Supplies Inc. - Medical Equipment Purchase"],
        "amount": [500.00],
        "transaction_date": ["2023-10-15"],
    }
    df = pd.DataFrame(test_data)

    print(
        f"Testing transaction classifier with medical transaction: {test_data['description'][0]}"
    )

    # Process the transaction with force processing to ensure AI is used
    result_df, stats = classifier.process_transactions(
        df,
        process_passes=(True, True, True),  # Process all passes
        force_process=True,  # Force AI processing
        batch_size=1,
    )

    print("\nProcessing complete!")
    print(f"Stats: {stats}")

    # Get detailed information about the classification
    transaction_id = test_data["transaction_id"][0]
    classification_query = """
        SELECT * FROM transaction_classifications 
        WHERE transaction_id = ?
    """
    classification_result = classifier.db.execute_query(
        classification_query, (transaction_id,)
    )

    if classification_result:
        classification = classification_result[0]
        print("\nClassification Result:")
        for i, col in enumerate(classification):
            print(f"Column {i}: {col}")
    else:
        print("No classification result found")

    # Print the prompt that was used for category determination
    print("\nPrompt used for Category Determination:")
    category_prompt = classifier._build_category_prompt(
        description=test_data["description"][0],
        amount=test_data["amount"][0],
        date=test_data["transaction_date"][0],
    )
    print(category_prompt)

    # Print the prompt that was used for tax classification
    print("\nPrompt used for Tax Classification:")
    # First build a test transaction info object
    from dataextractai.models.ai_responses import PayeeResponse, CategoryResponse
    from dataextractai.agents.transaction_classifier import TransactionInfo

    test_transaction = TransactionInfo(
        transaction_id=test_data["transaction_id"][0],
        description=test_data["description"][0],
        amount=test_data["amount"][0],
        transaction_date=test_data["transaction_date"][0],
        payee_info=PayeeResponse(
            payee="Medical Supplies Inc.",
            confidence="high",
            reasoning="Clear from description",
            business_description="Medical equipment supplier",
        ),
        category_info=CategoryResponse(
            category="Supplies",
            expense_type="business",
            business_percentage=100,
            notes="Medical equipment is a business supply",
            confidence="high",
        ),
    )

    classification_prompt = classifier._build_classification_prompt(
        transaction_description=test_data["description"][0],
        payee="Medical Supplies Inc.",
        category="Supplies",
        amount=test_data["amount"][0],
        date=test_data["transaction_date"][0],
    )
    print(classification_prompt)

    # Print available categories
    print("\nAvailable Tax Categories:")
    for cat_id, (name, worksheet) in classifier.business_categories_by_id.items():
        print(f"{cat_id}: {name} (Worksheet: {worksheet})")

    # Directly test an "advertising" prompt to compare
    print(
        "\nTesting with a transaction from a medical vendor that might be misclassified as advertising:"
    )

    # Create test transaction data for the problematic case
    problem_data = {
        "transaction_id": ["TEST002"],
        "description": ["Medical Provider Marketing Services"],
        "amount": [500.00],
        "transaction_date": ["2023-10-15"],
    }
    df_problem = pd.DataFrame(problem_data)

    # Process the transaction with force processing
    result_df_problem, _ = classifier.process_transactions(
        df_problem,
        process_passes=(True, True, True),
        force_process=True,
        batch_size=1,
    )


if __name__ == "__main__":
    test_medical_transaction()
