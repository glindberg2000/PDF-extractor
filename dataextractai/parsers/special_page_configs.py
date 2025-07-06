# Special extraction configs for problematic or complex pages
# Keyed by form_code or unique identifier from TOC/manifest

special_page_configs = {
    # Example: 6A Form (Business Expenses and Property & Equip.)
    "6A": {
        "Expenses": {
            "method": "vision",
            "crop": {"top": 0.19, "bottom": 0.586, "left": 0.0, "right": 1.0},
        },
        "Other_Expenses": {
            "method": "vision",
            "crop": {"top": 0.586, "bottom": 0.72, "left": 0.0, "right": 1.0},
        },
    },
    # Add more as needed
}
