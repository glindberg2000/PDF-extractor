"""Tax worksheet categories and configuration."""

from typing import Dict, List

TAX_WORKSHEET_CATEGORIES = {
    "6A": {  # Main Business Expenses Worksheet
        "main_expenses": {  # Fixed IRS Schedule C categories
            "Advertising": {
                "description": "Promotional materials, online ads, marketing costs",
                "line_number": 8,
            },
            "Car_and_truck_expenses": {
                "description": "Vehicle expenses not claimed on Vehicle worksheet",
                "line_number": 9,
            },
            "Parking_fees_and_tolls": {
                "description": "Business-related parking and toll charges",
                "line_number": 9,  # Part of car expenses
            },
            "Commissions_and_fees": {
                "description": "Sales commissions and service fees paid",
                "line_number": 10,
            },
            "Contract_labor": {
                "description": "Payments to independent contractors",
                "line_number": 11,
            },
            "Employee_benefit_programs": {
                "description": "Health insurance and other employee benefits",
                "line_number": 14,
            },
            "Insurance_non_health": {
                "description": "Business insurance excluding health insurance",
                "line_number": 15,
            },
            "Interest_mortgage": {
                "description": "Mortgage interest paid to banks",
                "line_number": "16a",
            },
            "Interest_other": {
                "description": "Other business interest payments",
                "line_number": "16b",
            },
            "Legal_and_professional_fees": {
                "description": "Attorney, accountant, and consulting fees",
                "line_number": 17,
            },
            "Office_expense": {
                "description": "General office expenses and supplies",
                "line_number": 18,
            },
            "Pension_and_profit_sharing": {
                "description": "Retirement plan contributions",
                "line_number": 19,
            },
            "Rent_lease_vehicles": {
                "description": "Vehicle, machinery, equipment rental",
                "line_number": "20a",
            },
            "Rent_lease_other": {
                "description": "Other business property rental",
                "line_number": "20b",
            },
            "Repairs_and_maintenance": {
                "description": "Business property and equipment repairs",
                "line_number": 21,
            },
            "Supplies": {
                "description": "Business supplies not included in COGS",
                "line_number": 22,
            },
            "Taxes_and_licenses": {
                "description": "Business taxes and license fees",
                "line_number": 23,
            },
            "Travel": {"description": "Business travel expenses", "line_number": "24a"},
            "Meals": {
                "description": "Business meals (50% deductible)",
                "line_number": "24b",
            },
            "Entertainment": {
                "description": "Business entertainment (state returns only)",
                "line_number": "Other",
            },
            "Utilities": {
                "description": "Business utilities not claimed on home office",
                "line_number": 25,
            },
            "Wages": {"description": "Employee salary and wages", "line_number": 26},
            "Dependent_care_benefits": {
                "description": "Employee dependent care assistance",
                "line_number": 27,
            },
        }
    },
    "Vehicle": {  # Vehicle Worksheet
        "expenses": {
            "Mileage_business": {
                "description": "Business miles driven",
                "calculation": "standard_mileage_rate",
            },
            "Mileage_personal": {
                "description": "Personal miles driven",
                "tracking_only": True,
            },
            "Gas": {"description": "Fuel costs", "actual_expenses": True},
            "Insurance": {"description": "Vehicle insurance", "actual_expenses": True},
            "Registration": {
                "description": "Vehicle registration fees",
                "actual_expenses": True,
            },
            "Repairs": {
                "description": "Vehicle maintenance and repairs",
                "actual_expenses": True,
            },
            "Lease_payments": {
                "description": "Vehicle lease payments",
                "actual_expenses": True,
            },
        }
    },
    "HomeOffice": {  # Home Office Worksheet (Form 8829)
        "expenses": {
            "Rent": {
                "description": "Home rental payments",
                "direct_or_indirect": "indirect",
            },
            "Mortgage_interest": {
                "description": "Home mortgage interest",
                "direct_or_indirect": "indirect",
            },
            "Property_tax": {
                "description": "Real estate taxes",
                "direct_or_indirect": "indirect",
            },
            "Insurance": {
                "description": "Home insurance",
                "direct_or_indirect": "indirect",
            },
            "Utilities": {
                "description": "Utilities for entire home",
                "direct_or_indirect": "indirect",
            },
            "Repairs": {
                "description": "Home maintenance and repairs",
                "direct_or_indirect": "both",
            },
            "Depreciation": {
                "description": "Home office depreciation",
                "calculation": "depreciation_worksheet",
            },
        }
    },
}


def get_worksheet_for_category(category: str) -> str:
    """Determine which worksheet a category belongs to."""
    for worksheet, data in TAX_WORKSHEET_CATEGORIES.items():
        for section in data.values():
            if category in section:
                return worksheet
    return "6A"  # Default to main worksheet if not found


def get_line_number(worksheet: str, category: str) -> int:
    """Get the line number for a category on its worksheet."""
    if worksheet not in TAX_WORKSHEET_CATEGORIES:
        return 0

    for section in TAX_WORKSHEET_CATEGORIES[worksheet].values():
        if category in section:
            return section[category].get("line_number", 0)
    return 0


def is_valid_category(category: str) -> bool:
    """Check if a category is valid in any worksheet."""
    for worksheet_data in TAX_WORKSHEET_CATEGORIES.values():
        for section in worksheet_data.values():
            if category in section:
                return True
    return False


def get_all_categories() -> List[str]:
    """Get a list of all available categories across all worksheets."""
    categories = []
    for worksheet_data in TAX_WORKSHEET_CATEGORIES.values():
        for section in worksheet_data.values():
            categories.extend(section.keys())
    return categories


def get_category_info(category: str) -> Dict:
    """Get detailed information about a category."""
    for worksheet_data in TAX_WORKSHEET_CATEGORIES.values():
        for section in worksheet_data.values():
            if category in section:
                return section[category]
    return {}
