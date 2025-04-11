from django.contrib import admin
from .models import BusinessProfile, ClientExpenseCategory, Transaction


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("client_id", "business_type")
    search_fields = ("client_id", "business_description")


@admin.register(ClientExpenseCategory)
class ClientExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name", "client", "category_type", "tax_year", "worksheet")
    list_filter = ("category_type", "tax_year", "worksheet")
    search_fields = ("category_name", "description")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "transaction_date",
        "amount",
        "description",
        "file_path",
        "source",
        "transaction_type",
        "normalized_amount",
        "statement_start_date",
        "statement_end_date",
        "account_number",
        "transaction_id",
    )
    list_filter = ("transaction_date", "category", "source", "transaction_type")
    search_fields = (
        "description",
        "category",
        "source",
        "transaction_type",
        "account_number",
    )
