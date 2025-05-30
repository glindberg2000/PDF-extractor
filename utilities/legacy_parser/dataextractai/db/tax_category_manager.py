"""Database manager for tax categories."""

from typing import List, Optional, Tuple
import sqlite3
import logging
from dataextractai.utils.tax_categories import TAX_WORKSHEET_CATEGORIES

logger = logging.getLogger(__name__)

# Define the structure for the personal expense category
PERSONAL_EXPENSE_INFO = {"worksheet": "Personal", "category": "Personal Expense"}


class TaxCategoryManager:
    """Manages tax category operations in the database."""

    def __init__(self, db_path: str):
        """Initialize the tax category manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialize_categories()
        self._personal_category_id = None  # Cache the ID

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection.

        Returns:
            A SQLite database connection

        Raises:
            sqlite3.Error: If connection fails
        """
        try:
            return sqlite3.connect(self.db_path)
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise

    def _initialize_categories(self):
        """Initialize the tax categories table with predefined categories."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Drop table if exists to apply schema changes (Use with caution!)
            # cursor.execute("DROP TABLE IF EXISTS tax_categories")
            # logger.warning("Dropped existing tax_categories table for schema update.")

            # Create table with ID and is_personal flag
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tax_categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    worksheet TEXT NOT NULL,
                    category TEXT NOT NULL,
                    is_personal BOOLEAN DEFAULT FALSE NOT NULL,
                    UNIQUE(worksheet, category)
                )
            """
            )

            # Check if personal category already exists
            cursor.execute(
                "SELECT id FROM tax_categories WHERE worksheet = ? AND category = ?",
                (PERSONAL_EXPENSE_INFO["worksheet"], PERSONAL_EXPENSE_INFO["category"]),
            )
            personal_exists = cursor.fetchone()

            if not personal_exists:
                # Insert the dedicated personal category
                cursor.execute(
                    "INSERT INTO tax_categories (worksheet, category, is_personal) VALUES (?, ?, TRUE)",
                    (
                        PERSONAL_EXPENSE_INFO["worksheet"],
                        PERSONAL_EXPENSE_INFO["category"],
                    ),
                )
                logger.info(
                    f"Inserted personal expense category: {PERSONAL_EXPENSE_INFO['category']}"
                )

            # Insert predefined business categories
            inserted_count = 0
            for worksheet, categories in TAX_WORKSHEET_CATEGORIES.items():
                for category in categories:
                    try:
                        cursor.execute(
                            "INSERT OR IGNORE INTO tax_categories (worksheet, category, is_personal) VALUES (?, ?, FALSE)",
                            (worksheet, category),
                        )
                        if cursor.rowcount > 0:
                            inserted_count += 1
                    except sqlite3.IntegrityError:
                        # This handles the UNIQUE constraint if somehow IGNORE fails in edge cases
                        logger.debug(
                            f"Category '{category}' on worksheet '{worksheet}' already exists."
                        )

            conn.commit()
            if inserted_count > 0:
                logger.info(
                    f"Inserted or verified {inserted_count} business tax categories."
                )
            else:
                logger.info("Tax categories already initialized.")

        except sqlite3.Error as e:
            logger.error(f"Error initializing tax categories: {e}")
            # Consider if raising is appropriate or if fallback is needed
            # raise # Re-raise if initialization is critical

        finally:
            conn.close()

    def get_personal_expense_category(self) -> Optional[Tuple[int, str, str]]:
        """Get the ID, name, and worksheet of the dedicated personal expense category."""
        if self._personal_category_id is not None:
            # Use cached ID if available
            conn = self._get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(
                    "SELECT id, worksheet, category FROM tax_categories WHERE id = ?",
                    (self._personal_category_id,),
                )
                result = cursor.fetchone()
                if result:
                    return result  # Returns (id, worksheet, category)
            except sqlite3.Error as e:
                logger.error(
                    f"Error fetching cached personal category {self._personal_category_id}: {e}"
                )
            finally:
                conn.close()
                # Fall through to query by name if cache lookup failed

        # Query by name if not cached or cache failed
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, worksheet, category FROM tax_categories WHERE worksheet = ? AND category = ? AND is_personal = TRUE",
                (PERSONAL_EXPENSE_INFO["worksheet"], PERSONAL_EXPENSE_INFO["category"]),
            )
            result = cursor.fetchone()
            if result:
                self._personal_category_id = result[0]  # Cache the ID
                return result  # Returns (id, worksheet, category)
            else:
                logger.error("Personal expense category not found in database!")
                return None
        except sqlite3.Error as e:
            logger.error(f"Error retrieving personal expense category: {e}")
            return None
        finally:
            conn.close()

    def get_all_business_categories(self) -> List[Tuple[int, str, str]]:
        """Get all business tax categories (ID, worksheet, category)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, worksheet, category FROM tax_categories WHERE is_personal = FALSE ORDER BY worksheet, category"
            )
            categories = cursor.fetchall()
            return categories
        except sqlite3.Error as e:
            logger.error(f"Error getting all business categories: {e}")
            return []
        finally:
            conn.close()

    def get_categories_for_worksheet(self, worksheet: str) -> List[str]:
        """Get all tax categories for a specific worksheet.

        Args:
            worksheet: The worksheet identifier (e.g., 'T2125', 'T776')

        Returns:
            List of category names
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT category FROM tax_categories WHERE worksheet = ? ORDER BY category",
                (worksheet,),
            )
            categories = [row[0] for row in cursor.fetchall()]

            return categories

        except sqlite3.Error as e:
            logger.error(f"Error getting categories for worksheet {worksheet}: {e}")
            return []

        finally:
            conn.close()

    def get_worksheet_for_category(self, category: str) -> Optional[str]:
        """Get the worksheet associated with a tax category.

        Args:
            category: The tax category name

        Returns:
            The worksheet identifier or None if not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT worksheet FROM tax_categories WHERE category = ?", (category,)
            )
            result = cursor.fetchone()

            return result[0] if result else None

        except sqlite3.Error as e:
            logger.error(f"Error getting worksheet for category {category}: {e}")
            return None

        finally:
            conn.close()

    def get_all_categories(self) -> List[Tuple[int, str, str, bool]]:
        """Get all tax categories (ID, worksheet, category, is_personal)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, worksheet, category, is_personal FROM tax_categories ORDER BY is_personal DESC, worksheet, category"
            )
            categories = cursor.fetchall()
            return categories
        except sqlite3.Error as e:
            logger.error(f"Error getting all categories: {e}")
            return []
        finally:
            conn.close()

    def add_category(
        self, worksheet: str, category: str, is_personal: bool = False
    ) -> Optional[int]:
        """Add a new tax category. Defaults to business category.

        Args:
            worksheet: The worksheet identifier
            category: The category name
            is_personal: Flag indicating if it's a personal category

        Returns:
            The ID of the newly added category, or None if failed.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO tax_categories (worksheet, category, is_personal) VALUES (?, ?, ?)",
                (worksheet, category, is_personal),
            )
            conn.commit()
            new_id = cursor.lastrowid
            logger.info(
                f"Added tax category '{category}' (ID: {new_id}) for worksheet '{worksheet}', Personal: {is_personal}"
            )
            return new_id
        except sqlite3.IntegrityError:
            logger.warning(
                f"Category '{category}' already exists for worksheet '{worksheet}'."
            )
            # Optionally retrieve and return the existing ID
            cursor.execute(
                "SELECT id FROM tax_categories WHERE worksheet=? AND category=?",
                (worksheet, category),
            )
            existing = cursor.fetchone()
            return existing[0] if existing else None
        except sqlite3.Error as e:
            logger.error(
                f"Error adding category {category} to worksheet {worksheet}: {e}"
            )
            return None
        finally:
            conn.close()

    def remove_category(self, category_id: int) -> bool:
        """Remove a tax category by its ID. Cannot remove the Personal Expense category."""

        # Prevent deletion of the core Personal Expense category
        personal_cat_info = self.get_personal_expense_category()
        if personal_cat_info and category_id == personal_cat_info[0]:
            logger.error("Cannot remove the default 'Personal Expense' category.")
            return False

        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # First, check if the category exists
            cursor.execute(
                "SELECT category FROM tax_categories WHERE id = ?", (category_id,)
            )
            category_exists = cursor.fetchone()
            if not category_exists:
                logger.warning(
                    f"Category with ID {category_id} not found. Cannot remove."
                )
                return False

            # Proceed with deletion
            cursor.execute("DELETE FROM tax_categories WHERE id = ?", (category_id,))
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Removed tax category with ID: {category_id}")
                return True
            else:
                # Should not happen if existence check passed, but good to handle
                logger.warning(
                    f"Category with ID {category_id} could not be removed (already deleted?)."
                )
                return False

        except sqlite3.Error as e:
            logger.error(f"Error removing category with ID {category_id}: {e}")
            return False
        finally:
            conn.close()
