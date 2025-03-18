"""add default statement types

Revision ID: 004
Revises: cc199066cf64
Create Date: 2024-03-17 16:50:00.000000

"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = "004"
down_revision = "cc199066cf64"
branch_labels = None
depends_on = None


def upgrade():
    # Get database connection
    conn = op.get_bind()

    # Get current timestamp
    now = datetime.utcnow()

    # Insert default statement types
    conn.execute(
        sa.text(
            """
        INSERT INTO statement_types (name, description, is_active, created_at, updated_at)
        VALUES 
            ('Bank Statement', 'Regular bank account statements', 1, :now, :now),
            ('Credit Card', 'Credit card statements', 1, :now, :now),
            ('Investment', 'Investment account statements', 1, :now, :now)
        """
        ),
        {"now": now},
    )


def downgrade():
    # Get database connection
    conn = op.get_bind()

    # Delete default statement types
    conn.execute(
        sa.text(
            """
        DELETE FROM statement_types 
        WHERE name IN ('Bank Statement', 'Credit Card', 'Investment')
        """
        )
    )
