"""
Pydantic models for AI classification responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict
from dataclasses import dataclass
from ..utils.tax_categories import TAX_WORKSHEET_CATEGORIES


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
    worksheet: Literal["6A", "Vehicle", "HomeOffice"] = Field(
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
