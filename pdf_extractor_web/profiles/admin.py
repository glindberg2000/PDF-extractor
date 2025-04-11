from django.contrib import admin
from .models import (
    BusinessProfile,
    ClientExpenseCategory,
    Transaction,
    LLMConfig,
    Agent,
    Tool,
)
from django.utils.translation import gettext_lazy as _


@admin.register(BusinessProfile)
class BusinessProfileAdmin(admin.ModelAdmin):
    list_display = ("client_id", "business_type")
    search_fields = ("client_id", "business_description")


@admin.register(ClientExpenseCategory)
class ClientExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ("category_name", "client", "category_type", "tax_year", "worksheet")
    list_filter = ("category_type", "tax_year", "worksheet")
    search_fields = ("category_name", "description")


class ClientFilter(admin.SimpleListFilter):
    title = _("client")
    parameter_name = "client"

    def lookups(self, request, model_admin):
        clients = set(Transaction.objects.values_list("client__client_id", flat=True))
        return [(client, client) for client in clients]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(client__client_id=self.value())
        return queryset


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
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
    list_filter = (
        ClientFilter,
        "transaction_date",
        "category",
        "source",
        "transaction_type",
    )
    search_fields = (
        "description",
        "category",
        "source",
        "transaction_type",
        "account_number",
    )


@admin.register(LLMConfig)
class LLMConfigAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "url")
    search_fields = ("provider", "model")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "purpose", "llm")
    search_fields = ("name", "purpose", "llm__name")
    filter_horizontal = ("tools",)


@admin.register(Tool)
class ToolAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "module_path")
    search_fields = ("name", "description", "module_path")
