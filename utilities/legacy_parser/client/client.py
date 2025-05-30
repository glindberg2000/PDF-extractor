from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ClientConfig:
    """Client configuration data model."""

    client_name: str
    business_type: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    annual_revenue: Optional[str] = None
    employee_count: Optional[int] = None
    business_activities: List[str] = field(default_factory=list)
    typical_expenses: List[str] = field(default_factory=list)
    industry_keywords: dict = field(default_factory=dict)  # Maps keywords to weights
    last_updated: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "client_name": self.client_name,
            "business_details": {
                "business_type": self.business_type,
                "industry": self.industry,
                "location": self.location,
                "annual_revenue": self.annual_revenue,
                "employee_count": self.employee_count,
                "business_activities": self.business_activities,
                "typical_expenses": self.typical_expenses,
                "industry_keywords": self.industry_keywords,
            },
            "last_updated": self.last_updated.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    def from_dict(cls, data):
        """Create from dictionary after deserialization."""
        business_details = data.get("business_details", {})
        return cls(
            client_name=data.get("client_name", ""),
            business_type=business_details.get("business_type"),
            industry=business_details.get("industry"),
            location=business_details.get("location"),
            annual_revenue=business_details.get("annual_revenue"),
            employee_count=business_details.get("employee_count"),
            business_activities=business_details.get("business_activities", []),
            typical_expenses=business_details.get("typical_expenses", []),
            industry_keywords=business_details.get("industry_keywords", {}),
            last_updated=datetime.strptime(
                data.get("last_updated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "%Y-%m-%d %H:%M:%S",
            ),
        )
