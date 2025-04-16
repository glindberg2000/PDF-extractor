# Classification Data Storage Issue

## Problem Description
Transactions are being classified by the AI, but the classification data is not being properly stored or displayed in the admin interface. The API is returning correct data, but it's not persisting in the database.

## Current State
1. API is successfully classifying transactions and returning data in the correct format:
```json
{
    "classification_type": "business",
    "worksheet": "None",
    "irs_category": "Supplies",
    "confidence": "medium",
    "reasoning": "This transaction is a purchase at Lowe's...",
    "questions": "What specific items were purchased at Lowe's..."
}
```

2. Database Schema:
```python
class SimpleClassification2(models.Model):
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="simple_class2"
    )
    classification_type = models.CharField(
        max_length=50,
        choices=[("business", "Business"), ("personal", "Personal")],
    )
    worksheet = models.CharField(
        max_length=50,
        choices=[
            ("6A", "6A"),
            ("Auto", "Auto"),
            ("HomeOffice", "HomeOffice"),
            ("None", "None"),
        ],
    )
    confidence = models.CharField(
        max_length=20,
        choices=[("high", "High"), ("medium", "Medium"), ("low", "Low")],
    )
    reasoning = models.TextField()
    questions = models.TextField(blank=True, null=True)
    classification_method = models.CharField(
        max_length=20,
        choices=[("AI", "AI Classification"), ("Human", "Human Override")],
        default="AI",
    )
```

3. Current Storage Logic:
```python
# Create or update classification
classification_data = {
    "classification_type": result["classification_type"],
    "worksheet": result["worksheet"],
    "confidence": result["confidence"],
    "reasoning": result["reasoning"],
    "questions": result["questions"],
    "classification_method": "AI",
}

# Create or update the classification
SimpleClassification2.objects.update_or_create(
    transaction=transaction, defaults=classification_data
)
```

## Django Configuration
1. Database Settings:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'pdf_extractor',
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

2. Installed Apps:
```python
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'profiles',
]
```

3. Admin Configuration:
```python
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "amount",
        "description",
        "payee",
        "normalized_description",
        "transaction_type",
        "get_classification_type",
        "get_worksheet",
        "get_classification_method",
        "get_confidence",
        "get_classification_reasoning",
        "get_questions",
    )
    list_filter = (
        ClientFilter,
        "transaction_date",
        "source",
        "transaction_type",
        "simple_class2__confidence",
        "simple_class2__classification_method",
    )
    search_fields = (
        "description",
        "source",
        "transaction_type",
        "account_number",
        "payee",
        "normalized_description",
        "simple_class2__classification_type",
        "simple_class2__worksheet",
        "simple_class2__reasoning",
        "simple_class2__questions",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("simple_class2")
```

4. Transaction Isolation Level:
```python
DATABASES = {
    'default': {
        # ... other settings ...
        'OPTIONS': {
            'isolation_level': 'read committed',
        },
    }
}
```

5. Logging Configuration:
```python
# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set to DEBUG to see all messages

# Create handlers
console_handler = logging.StreamHandler()
file_handler = logging.FileHandler("classification.log")

# Set log levels
console_handler.setLevel(logging.INFO)
file_handler.setLevel(logging.DEBUG)

# Create formatters
console_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
file_formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d"
)

# Add formatters to handlers
console_handler.setFormatter(console_formatter)
file_handler.setFormatter(file_formatter)

# Add handlers to logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Prevent duplicate logging
logger.propagate = False
```

## Symptoms
1. API calls are successful and return valid data
2. Logs show the data is being parsed correctly
3. The update_or_create operation appears to complete without errors
4. However, the data is not visible in the admin interface
5. The transaction shows as "Not Classified" in the admin list view

## Questions for Review
1. Is the OneToOne relationship between Transaction and SimpleClassification2 working correctly?
2. Are there any database constraints or triggers that might be preventing the insert?
3. Could there be a transaction rollback happening silently?
4. Is the select_related("simple_class2") in the admin queryset working as expected?
5. Are there any permission issues with the database operations?
6. Is the transaction isolation level causing any issues with the OneToOne relationship?
7. Are there any Django middleware or signals that might be interfering with the save operation?
8. Is the logging configuration preventing us from seeing database errors?
9. Are we missing any critical log levels or handlers that could reveal the issue?

## Next Steps
1. Add more detailed logging around the database operations
2. Check if the SimpleClassification2 records are actually being created
3. Verify the database permissions
4. Consider adding a database trigger to log all insert/update operations
5. Review the transaction isolation level settings
6. Check Django's database transaction management
7. Verify that no middleware is interfering with the save operation
8. Add SQL query logging to see the actual database operations
9. Consider adding a database-level audit trigger

## Request for Additional Eyes
We need help identifying why the data isn't persisting despite the API and code appearing to work correctly. Any insights into potential database or Django ORM issues would be appreciated. 