"""Models for worksheet assignment and tax categorization."""

from dataclasses import dataclass
from typing import Optional, List, Dict
from decimal import Decimal


@dataclass
class WorksheetAssignment:
    """Result of worksheet assignment for a transaction."""

    worksheet: str
    tax_category: str
    tax_subcategory: Optional[str]
    line_number: str
    confidence: str
    reasoning: str
    needs_splitting: bool = False
    split_details: Optional[Dict] = None


@dataclass
class SplitResult:
    """Result of transaction splitting analysis."""

    should_split: bool
    splits: List[Dict[str, any]]  # List of worksheet assignments with amounts
    confidence: str
    reasoning: str


@dataclass
class YearOverYearComparison:
    """Year-over-year comparison for a transaction category."""

    current_year_amount: Decimal
    previous_year_amount: Optional[Decimal]
    variance_amount: Optional[Decimal]
    variance_percentage: Optional[float]
    is_significant: bool
    reasoning: str
    suggested_review: bool


@dataclass
class WorksheetPrompt:
    """Prompt configuration for worksheet assignment."""

    transaction_description: str
    transaction_amount: Decimal
    base_category: str
    payee: str
    date: str
    previous_assignments: Optional[List[Dict]] = None  # Historical assignments
    business_context: Optional[str] = None
    special_rules: Optional[Dict] = None
