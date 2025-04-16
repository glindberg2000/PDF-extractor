from django.db import models
from profiles.models import Transaction


class SimpleClassification2(models.Model):
    """
    New, simpler classification model with a clean OneToOne relationship.
    This is a separate table that won't affect existing data.
    """

    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="simple_class2"
    )
    classification_type = models.CharField(
        max_length=50,
        choices=[("business", "Business"), ("personal", "Personal")],
        help_text="Type of classification (business or personal)",
    )
    worksheet = models.CharField(
        max_length=50,
        choices=[
            ("6A", "6A"),
            ("Auto", "Auto"),
            ("HomeOffice", "HomeOffice"),
            ("None", "None"),
        ],
        help_text="Tax worksheet category",
    )
    confidence = models.CharField(
        max_length=20,
        choices=[("high", "High"), ("medium", "Medium"), ("low", "Low")],
        help_text="Confidence level of the classification",
    )
    reasoning = models.TextField(
        help_text="Explanation for the classification decision"
    )
    questions = models.TextField(
        blank=True,
        null=True,
        help_text="Any questions or uncertainties about this classification",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction} - {self.classification_type} ({self.worksheet})"
