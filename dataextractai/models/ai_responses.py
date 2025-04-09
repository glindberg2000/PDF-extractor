"""
Pydantic models for AI classification responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from dataclasses import dataclass
from ..utils.tax_categories import TAX_WORKSHEET_CATEGORIES
from enum import Enum, auto


class PayeeResponse(BaseModel):
    """Response model for payee identification."""

    payee: str = Field(..., description="Identified payee/merchant name")
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Confidence level in the identification"
    )
    reasoning: str = Field(..., description="Explanation of the identification")
    business_description: Optional[str] = Field(
        None, description="Description of what type of business this payee is"
    )
    general_category: Optional[str] = Field(
        None, description="General expense category for this transaction"
    )

    def as_dict(self, prefix: str = "") -> Dict[str, Any]:
        return {
            f"{prefix}_payee": self.payee,
            f"{prefix}_confidence": self.confidence,
            f"{prefix}_reasoning": self.reasoning,
            f"{prefix}_business_description": self.business_description,
            f"{prefix}_general_category": self.general_category,
        }


@dataclass
class CategoryResponse:
    """Response from category assignment step."""

    category: str
    expense_type: str
    business_percentage: int
    notes: str
    # Optional fields for precise mode
    confidence: str = "medium"
    detailed_context: str = ""

    def as_dict(self, prefix: str = "") -> Dict[str, Any]:
        """Convert to dictionary with optional prefix for key names."""
        prefix = f"{prefix}_" if prefix else ""
        return {
            f"{prefix}category": self.category,
            f"{prefix}expense_type": self.expense_type,
            f"{prefix}business_percentage": self.business_percentage,
            f"{prefix}category_reasoning": self.notes,
            f"{prefix}category_confidence": self.confidence,
            f"{prefix}business_context": self.detailed_context,
        }


# Build numbered tax categories mapping
TAX_CATEGORIES_BY_ID: Dict[int, str] = {}
CATEGORY_IDS_BY_NAME: Dict[str, int] = {}
current_id = 1

for worksheet, categories in TAX_WORKSHEET_CATEGORIES.items():
    # Handle categories as a list
    if isinstance(categories, list):
        for category_name in categories:
            TAX_CATEGORIES_BY_ID[current_id] = category_name
            CATEGORY_IDS_BY_NAME[category_name] = current_id
            current_id += 1
    # Handle categories as a dict (for future compatibility)
    elif isinstance(categories, dict):
        for section in categories.values():
            for category_name in section.keys():
                TAX_CATEGORIES_BY_ID[current_id] = category_name
                CATEGORY_IDS_BY_NAME[category_name] = current_id
                current_id += 1


class ClassificationResponse(BaseModel):
    """Response model for tax classification."""

    tax_category_id: int = Field(
        ...,
        description="ID of the tax category (1-N)",
        ge=1,
        le=len(TAX_CATEGORIES_BY_ID),
    )
    business_percentage: int = Field(
        ..., description="Business use percentage", ge=0, le=100
    )
    worksheet: Literal["6A", "Vehicle", "HomeOffice", "Personal"] = Field(
        ..., description="Tax worksheet designation"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Confidence level in the classification"
    )
    reasoning: str = Field(..., description="Explanation of the classification")
    tax_implications: Optional[str] = Field(
        None, description="Tax implications if relevant"
    )

    class Config:
        """Pydantic model configuration."""

        frozen = True
        strict = True
        extra = "forbid"

    @property
    def tax_category(self) -> str:
        """Get the tax category name from the ID."""
        return TAX_CATEGORIES_BY_ID[self.tax_category_id]
