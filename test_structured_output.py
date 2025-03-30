from dataextractai.agents.transaction_classifier import TransactionClassifier


def main():
    classifier = TransactionClassifier("Tim_Valenti", model_type="fast")
    result = classifier.test_structured_output()
    print(f"Test completed successfully: {result}")


if __name__ == "__main__":
    main()
