from django.core.management.base import BaseCommand
from profiles.models import Transaction


class Command(BaseCommand):
    help = "Check transaction data in the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "search_term",
            nargs="?",
            type=str,
            help="Optional search term to filter transactions",
        )

    def handle(self, *args, **options):
        search_term = options.get("search_term")

        self.stdout.write("\n=== Transaction Data Check ===")

        # Get all transactions or filter by search term
        if search_term:
            transactions = Transaction.objects.filter(
                description__icontains=search_term
            )
            self.stdout.write(
                f"\nFound {transactions.count()} transactions containing '{search_term}'"
            )
        else:
            transactions = Transaction.objects.all()
            self.stdout.write(f"\nFound {transactions.count()} total transactions")

        # Display transaction details
        for tx in transactions:
            self.stdout.write("\nTransaction Details:")
            self.stdout.write(f"ID: {tx.id}")
            self.stdout.write(f"Description: {tx.description}")
            self.stdout.write(f"Payee: {tx.payee}")
            self.stdout.write(f"Classification Type: {tx.classification_type}")
            self.stdout.write(f"Worksheet: {tx.worksheet}")
            self.stdout.write(f"Business Percentage: {tx.business_percentage}")
            self.stdout.write(f"Confidence: {tx.confidence}")
            self.stdout.write(f"Classification Method: {tx.classification_method}")
            self.stdout.write(f"Payee Extraction Method: {tx.payee_extraction_method}")
            self.stdout.write("-" * 50)
