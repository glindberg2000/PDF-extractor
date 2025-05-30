"""Constants shared across the application."""

# Mapping of category names to IDs
CATEGORY_MAPPING = {
    # Income categories
    "Business Income": 1,
    "Rent Income": 2,
    "Interest Income": 3,
    # Business expense categories
    "Advertising": 4,
    "Auto Expenses": 5,
    "Bank Fees": 6,
    "Commissions": 7,
    "Contract Labor": 8,
    "Depreciation": 9,
    "Meals": 10,
    "Insurance": 11,
    "Interest Paid": 12,
    "Legal Services": 13,
    "Office Expenses": 14,
    "Office Rent": 15,
    "Office Supplies": 16,
    "Office Utilities": 17,
    "Postage": 18,
    "Professional Dues": 19,
    "Professional Services": 20,
    "Repairs": 21,
    "Supplies": 22,
    "Travel": 23,
    "Wages": 24,
    "Other Expenses": 25,
    "Tax Payments": 26,
    "Home Office": 27,
    "Vehicle": 28,
    # Non-business categories
    "Personal": 29,
    "Transfer": 30,
}

# Reverse mapping (ID to name)
CATEGORY_ID_TO_NAME = {str(v): k for k, v in CATEGORY_MAPPING.items()}
CATEGORY_ID_TO_NAME.update(
    {v: k for k, v in CATEGORY_MAPPING.items()}
)  # Add numeric version too
CATEGORY_ID_TO_NAME.update(
    {float(v): k for k, v in CATEGORY_MAPPING.items()}
)  # Add float version too

# Allowed worksheets for tax categories
ALLOWED_WORKSHEETS = {"Personal", "6A", "Vehicle", "HomeOffice"}
