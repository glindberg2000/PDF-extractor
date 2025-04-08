"""
Tax worksheet categories for different tax forms.
"""

from typing import Dict, List

# T2125 - Statement of Business or Professional Activities
T2125_CATEGORIES = [
    "Advertising",
    "Meals and entertainment",
    "Bad debts",
    "Insurance",
    "Interest and bank charges",
    "Business taxes, licenses, and memberships",
    "Office expenses",
    "Supplies",
    "Professional fees",
    "Management and administration fees",
    "Rent",
    "Repairs and maintenance",
    "Salaries, wages, and benefits",
    "Travel",
    "Telephone and utilities",
    "Fuel costs",
    "Delivery, freight, and express",
    "Motor vehicle expenses",
    "Capital cost allowance",
    "Other expenses",
]

# T776 - Statement of Real Estate Rentals
T776_CATEGORIES = [
    "Advertising",
    "Insurance",
    "Interest and bank charges",
    "Office expenses",
    "Professional fees",
    "Management and administration fees",
    "Repairs and maintenance",
    "Salaries, wages, and benefits",
    "Property taxes",
    "Travel",
    "Utilities",
    "Motor vehicle expenses",
    "Capital cost allowance",
    "Other expenses",
]

# Dictionary mapping worksheet identifiers to their categories
TAX_WORKSHEET_CATEGORIES = {"T2125": T2125_CATEGORIES, "T776": T776_CATEGORIES}


def get_worksheet_for_category(category: str) -> str:
    """Determine which worksheet a category belongs to."""
    for worksheet, data in TAX_WORKSHEET_CATEGORIES.items():
        if category in data:
            return worksheet
    return "6A"  # Default to main worksheet if not found


def get_line_number(worksheet: str, category: str) -> int:
    """Get the line number for a category on its worksheet."""
    if worksheet not in TAX_WORKSHEET_CATEGORIES:
        return 0

    if isinstance(TAX_WORKSHEET_CATEGORIES[worksheet], list):
        if category in TAX_WORKSHEET_CATEGORIES[worksheet]:
            return TAX_WORKSHEET_CATEGORIES[worksheet].index(category) + 1
    elif isinstance(TAX_WORKSHEET_CATEGORIES[worksheet], dict):
        for section in TAX_WORKSHEET_CATEGORIES[worksheet].values():
            if category in section:
                return section[category].get("line_number", 0)
    return 0


def is_valid_category(category: str) -> bool:
    """Check if a category is valid in any worksheet."""
    for worksheet_data in TAX_WORKSHEET_CATEGORIES.values():
        if isinstance(worksheet_data, list) and category in worksheet_data:
            return True
        elif isinstance(worksheet_data, dict):
            for section in worksheet_data.values():
                if category in section:
                    return True
    return False


def get_all_categories() -> List[str]:
    """Get a list of all available categories across all worksheets."""
    categories = []
    for worksheet_data in TAX_WORKSHEET_CATEGORIES.values():
        if isinstance(worksheet_data, list):
            categories.extend(worksheet_data)
        elif isinstance(worksheet_data, dict):
            categories.extend(worksheet_data.keys())
    return categories


def get_category_info(category: str) -> Dict:
    """Get detailed information about a category."""
    for worksheet_data in TAX_WORKSHEET_CATEGORIES.values():
        if isinstance(worksheet_data, list) and category in worksheet_data:
            return {
                "worksheet": get_worksheet_for_category(category),
                "line_number": get_line_number(
                    get_worksheet_for_category(category), category
                ),
            }
        elif isinstance(worksheet_data, dict):
            for section in worksheet_data.values():
                if category in section:
                    return section[category]
    return {}
