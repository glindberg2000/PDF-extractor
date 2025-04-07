from dataextractai.agents.transaction_classifier import TransactionClassifier
from dataextractai.db.client_db import ClientDB


def main():
    db = ClientDB()
    classifier = TransactionClassifier("Tim_Valenti", db, model_type="fast")
    result = classifier.test_structured_output()
    print(f"Test completed successfully: {result}")


if __name__ == "__main__":
    main()
