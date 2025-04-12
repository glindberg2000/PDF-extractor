from django.db import models
import types
from jsonschema import validate, ValidationError
import logging
from django.utils import timezone

# Create your models here.


class BusinessProfile(models.Model):
    client_id = models.CharField(max_length=255, primary_key=True)
    business_type = models.TextField(blank=True, null=True)
    business_description = models.TextField(blank=True, null=True)
    contact_info = models.TextField(blank=True, null=True)
    common_business_expenses = models.TextField(blank=True, null=True)
    custom_6A_expense_categories = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.client_id


class ClientExpenseCategory(models.Model):
    client = models.ForeignKey(
        BusinessProfile, on_delete=models.CASCADE, related_name="expense_categories"
    )
    category_name = models.CharField(max_length=255)
    category_type = models.CharField(
        max_length=50,
        choices=[
            ("other_expense", "Other Expense"),
            ("custom_category", "Custom Category"),
        ],
    )
    description = models.TextField(blank=True, null=True)
    tax_year = models.IntegerField()
    worksheet = models.CharField(
        max_length=50,
        choices=[
            ("6A", "6A"),
            ("Auto", "Auto"),
            ("HomeOffice", "HomeOffice"),
            ("Personal", "Personal"),
            ("None", "None"),
        ],
    )
    parent_category = models.CharField(max_length=255, blank=True, null=True)
    line_number = models.CharField(max_length=50, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client", "category_name", "tax_year"],
                name="unique_client_category_year",
            )
        ]


class Transaction(models.Model):
    client = models.ForeignKey(
        BusinessProfile, on_delete=models.CASCADE, related_name="transactions"
    )
    transaction_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
    category = models.CharField(max_length=255, blank=True, null=True)
    parsed_data = models.JSONField(default=dict, blank=True)
    file_path = models.CharField(max_length=255, blank=True, null=True)
    source = models.CharField(max_length=255, blank=True, null=True)
    transaction_type = models.CharField(max_length=50, blank=True, null=True)
    normalized_amount = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    statement_start_date = models.DateField(blank=True, null=True)
    statement_end_date = models.DateField(blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.IntegerField(unique=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["client", "transaction_id"], name="unique_transaction"
            )
        ]

    def __str__(self):
        return f"{self.client.client_id} - {self.transaction_date} - {self.amount}"


class LLMConfig(models.Model):
    provider = models.CharField(max_length=255)
    model = models.CharField(max_length=255, unique=True)
    url = models.URLField(blank=True, null=True)

    def __str__(self):
        return self.model


class Tool(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    module_path = models.CharField(max_length=255, blank=True, null=True)
    code = models.TextField(blank=True, null=True)
    schema = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = timezone.now()
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)

    def get_module(self):
        if self.module_path:
            return __import__(self.module_path, fromlist=["search"])
        elif self.code:
            # Create a temporary module from the code
            module = types.ModuleType(f"tool_{self.id}")
            exec(self.code, module.__dict__)
            return module
        return None

    def validate_schema(self, response):
        if self.schema:
            try:
                validate(instance=response, schema=self.schema)
                return True
            except ValidationError as e:
                logger.error(f"Schema validation failed for tool {self.name}: {e}")
                return False
        return True

    def execute(self, *args, **kwargs):
        module = self.get_module()
        if not module:
            raise ValueError(f"Tool {self.name} has no valid implementation")

        if not hasattr(module, "search"):
            raise ValueError(f"Tool {self.name} does not implement search function")

        result = module.search(*args, **kwargs)
        if not self.validate_schema(result):
            raise ValueError(f"Tool {self.name} returned invalid response")

        return result


class Agent(models.Model):
    name = models.CharField(max_length=255)
    purpose = models.TextField()
    prompt = models.TextField()
    llm = models.ForeignKey(LLMConfig, on_delete=models.CASCADE, related_name="agents")
    tools = models.ManyToManyField(
        Tool, related_name="agents", blank=True
    )  # Add tools relationship

    def __str__(self):
        return self.name


class NormalizedVendorData(models.Model):
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="normalized_data"
    )
    normalized_name = models.CharField(max_length=255, blank=True, null=True)
    normalized_description = models.TextField(blank=True, null=True)
    transaction_type = models.CharField(max_length=50, blank=True, null=True)
    justification = models.TextField(blank=True, null=True)
    confidence = models.CharField(
        max_length=10,
        choices=[("high", "High"), ("medium", "Medium"), ("low", "Low")],
        default="medium",
    )
    tools_used = models.JSONField(
        default=dict, blank=True
    )  # Track which tools were used
    created_at = models.DateTimeField(
        auto_now_add=True, null=True
    )  # Allow null for existing rows
    updated_at = models.DateTimeField(
        auto_now=True, null=True
    )  # Allow null for existing rows

    def __str__(self):
        return f"Normalized data for {self.transaction.description}"
