"""Database manager for tax categories."""

from typing import List, Optional, Tuple
import sqlite3
import logging
from dataextractai.utils.tax_categories import TAX_WORKSHEET_CATEGORIES

logger = logging.getLogger(__name__)


class TaxCategoryManager:
    """Manages tax category operations in the database."""

    def __init__(self, db_path: str):
        """Initialize the tax category manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialize_categories()

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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS tax_categories (
                    worksheet TEXT NOT NULL,
                    category TEXT NOT NULL,
                    UNIQUE(worksheet, category)
                )
            """
            )

            # Insert predefined categories
            for worksheet, categories in TAX_WORKSHEET_CATEGORIES.items():
                for category in categories:
                    cursor.execute(
                        "INSERT OR IGNORE INTO tax_categories (worksheet, category) VALUES (?, ?)",
                        (worksheet, category),
                    )

            conn.commit()
            logger.info("Tax categories initialized successfully")

        except sqlite3.Error as e:
            logger.error(f"Error initializing tax categories: {e}")
            raise

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

    def get_all_categories(self) -> List[Tuple[str, str]]:
        """Get all tax categories and their associated worksheets.

        Returns:
            List of tuples containing (worksheet, category)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT worksheet, category FROM tax_categories ORDER BY worksheet, category"
            )
            categories = cursor.fetchall()

            return categories

        except sqlite3.Error as e:
            logger.error(f"Error getting all categories: {e}")
            return []

        finally:
            conn.close()

    def add_category(self, worksheet: str, category: str) -> bool:
        """Add a new tax category.

        Args:
            worksheet: The worksheet identifier
            category: The category name

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "INSERT INTO tax_categories (worksheet, category) VALUES (?, ?)",
                (worksheet, category),
            )
            conn.commit()

            logger.info(f"Added tax category {category} for worksheet {worksheet}")
            return True

        except sqlite3.Error as e:
            logger.error(
                f"Error adding category {category} to worksheet {worksheet}: {e}"
            )
            return False

        finally:
            conn.close()

    def remove_category(self, worksheet: str, category: str) -> bool:
        """Remove a tax category.

        Args:
            worksheet: The worksheet identifier
            category: The category name

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "DELETE FROM tax_categories WHERE worksheet = ? AND category = ?",
                (worksheet, category),
            )
            conn.commit()

            if cursor.rowcount > 0:
                logger.info(
                    f"Removed tax category {category} from worksheet {worksheet}"
                )
                return True
            else:
                logger.warning(
                    f"No tax category {category} found for worksheet {worksheet}"
                )
                return False

        except sqlite3.Error as e:
            logger.error(
                f"Error removing category {category} from worksheet {worksheet}: {e}"
            )
            return False

        finally:
            conn.close()
