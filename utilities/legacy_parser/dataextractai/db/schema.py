"""Database schema definitions."""

# ... existing code ...

TAX_CATEGORIES_TABLE = """
CREATE TABLE IF NOT EXISTS tax_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worksheet TEXT NOT NULL,
    category TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(worksheet, category)
);
"""

# ... existing code ...

TABLES = [
    # ... existing tables ...
    TAX_CATEGORIES_TABLE,
]
