"""
Pydantic models for AI classification responses.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


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


class CategoryResponse(BaseModel):
    """Response model for category assignment."""

    category: str = Field(..., description="Assigned category")
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Confidence level in the categorization"
    )
    reasoning: str = Field(..., description="Explanation of the categorization")
    suggested_new_category: Optional[str] = Field(
        None, description="Suggested new category if needed"
    )
    new_category_reasoning: Optional[str] = Field(
        None, description="Explanation for suggested new category"
    )


class ClassificationResponse(BaseModel):
    """Response model for business/personal classification."""

    classification: Literal["Business", "Personal", "Unclassified"] = Field(
        ..., description="Classification result"
    )
    confidence: Literal["high", "medium", "low"] = Field(
        ..., description="Confidence level in the classification"
    )
    reasoning: str = Field(..., description="Explanation of the classification")
    tax_implications: Optional[str] = Field(
        None, description="Tax implications if relevant"
    )
