from django.shortcuts import render, redirect
from django.contrib import messages
import csv
from .forms import TransactionCSVForm
from .models import Transaction, BusinessProfile
import logging
from django.views.generic import ListView

logger = logging.getLogger(__name__)

# Create your views here.


def upload_transactions(request):
    if request.method == "POST":
        form = TransactionCSVForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            decoded_file = csv_file.read().decode("utf-8").splitlines()
            reader = csv.DictReader(decoded_file)
            client = BusinessProfile.objects.get(client_id="Tim and Gene")
            for row in reader:
                try:
                    Transaction.objects.create(
                        client=client,
                        transaction_date=row["transaction_date"],
                        description=row["description"],
                        amount=row["amount"],
                        file_path=row["file_path"],
                        source=row["source"],
                        transaction_type=row["transaction_type"],
                        normalized_amount=row["normalized_amount"],
                        statement_start_date=row["statement_start_date"] or None,
                        statement_end_date=row["statement_end_date"] or None,
                        account_number=row["account_number"],
                        transaction_id=row["transaction_id"],
                    )
                except Exception as e:
                    logger.error(f"Error processing row {row}: {e}")
                    messages.error(request, f"Error processing row: {row}")
            messages.success(request, "Transactions uploaded successfully.")
            return redirect("profile-list")
    else:
        form = TransactionCSVForm()
    return render(request, "profiles/upload_transactions.html", {"form": form})


class BusinessProfileListView(ListView):
    model = BusinessProfile
    template_name = "profiles/profile_list.html"
    context_object_name = "profiles"
