import os
import django
import sys

# Set up Django environment
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_root)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pdf_extractor_web.settings")
django.setup()

from profiles.models import Transaction


def check_transactions(search_term=None):
    """Check transaction data in the database."""
    print("\n=== Transaction Data Check ===")

    # Get all transactions or filter by search term
    if search_term:
        transactions = Transaction.objects.filter(description__icontains=search_term)
        print(f"\nFound {transactions.count()} transactions containing '{search_term}'")
    else:
        transactions = Transaction.objects.all()
        print(f"\nFound {transactions.count()} total transactions")

    # Display transaction details
    for tx in transactions:
        print("\nTransaction Details:")
        print(f"ID: {tx.id}")
        print(f"Description: {tx.description}")
        print(f"Payee: {tx.payee}")
        print(f"Classification Type: {tx.classification_type}")
        print(f"Worksheet: {tx.worksheet}")
        print(f"Business Percentage: {tx.business_percentage}")
        print(f"Confidence: {tx.confidence}")
        print(f"Classification Method: {tx.classification_method}")
        print(f"Payee Extraction Method: {tx.payee_extraction_method}")
        print("-" * 50)


if __name__ == "__main__":
    # You can pass a search term as a command line argument
    search_term = sys.argv[1] if len(sys.argv) > 1 else None
    check_transactions(search_term)
