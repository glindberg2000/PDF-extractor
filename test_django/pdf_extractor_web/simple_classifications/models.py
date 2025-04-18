from django.db import models
from django.utils import timezone
from profiles.models import Transaction, IRSWorksheet, IRSExpenseCategory


class SimpleClassification(models.Model):
    """
    A simplified classification model that combines AI and manual classifications.
    Uses a one-to-one relationship with Transaction for a clear source of truth.
    """

    # Core relationship
    transaction = models.OneToOneField(
        Transaction, on_delete=models.CASCADE, related_name="simple_classification"
    )

    # Classification details
    classification_type = models.CharField(
        max_length=50,
        choices=[
            ("business", "Business"),
            ("personal", "Personal"),
            ("transfer", "Transfer"),
            ("ignore", "Ignore"),
        ],
        help_text="Primary classification of the transaction",
    )

    worksheet = models.ForeignKey(
        IRSWorksheet,
        on_delete=models.PROTECT,  # Don't allow worksheet deletion if transactions exist
        null=True,
        blank=True,
        help_text="Associated IRS worksheet (e.g., 6A, Auto, HomeOffice)",
    )

    category = models.ForeignKey(
        IRSExpenseCategory,
        on_delete=models.PROTECT,  # Don't allow category deletion if transactions exist
        null=True,
        blank=True,
        help_text="Specific expense category within the worksheet",
    )

    # Classification metadata
    confidence = models.CharField(
        max_length=20,
        choices=[
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
            ("manual", "Manual Override"),
        ],
        help_text="Confidence level in the classification",
    )

    reasoning = models.TextField(
        help_text="Explanation for the classification decision"
    )

    # Audit trail
    created_by = models.CharField(
        max_length=100, help_text="Agent or user who created this classification"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.CharField(
        max_length=100, help_text="Agent or user who last updated this classification"
    )
    updated_at = models.DateTimeField(auto_now=True)

    # History tracking
    is_current = models.BooleanField(
        default=True, help_text="Whether this is the current active classification"
    )
    previous_version = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="next_version",
        help_text="Link to the previous version of this classification",
    )
    version_notes = models.TextField(
        blank=True, help_text="Notes about why this version was created"
    )

    class Meta:
        indexes = [
            models.Index(fields=["transaction", "created_at"]),
            models.Index(fields=["classification_type"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["updated_at"]),
        ]
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.transaction} - {self.classification_type} ({self.worksheet})"

    def save(self, *args, **kwargs):
        if not self.pk and self.is_current:
            # If this is a new classification and it's marked as current,
            # update any existing current classification
            current = SimpleClassification.objects.filter(
                transaction=self.transaction, is_current=True
            ).first()

            if current:
                # Set this classification's previous version
                self.previous_version = current
                # Update the existing classification
                current.is_current = False
                current.save()

        super().save(*args, **kwargs)

    @property
    def history(self):
        """Get the complete history of classifications for this transaction."""
        history = []
        current = self
        while current:
            history.append(current)
            current = current.previous_version
        return history

    @property
    def version_number(self):
        """Get the version number of this classification."""
        return len(self.history)

    def create_new_version(self, **updates):
        """
        Create a new version of this classification with the specified updates.
        """
        if not self.is_current:
            raise ValueError(
                "Can only create new versions from the current classification"
            )

        # Create a new version with the current data
        new_version = SimpleClassification.objects.create(
            transaction=self.transaction,
            classification_type=updates.get(
                "classification_type", self.classification_type
            ),
            worksheet=updates.get("worksheet", self.worksheet),
            category=updates.get("category", self.category),
            confidence="manual",  # New versions are always manual
            reasoning=updates.get("reasoning", ""),
            created_by=updates.get("created_by", "system"),
            updated_by=updates.get("updated_by", "system"),
            is_current=True,
            previous_version=self,
            version_notes=updates.get("version_notes", ""),
        )

        # Mark this version as no longer current
        self.is_current = False
        self.save()

        return new_version
