"""update statement types and categories

Revision ID: 005
Revises: 004
Create Date: 2024-03-21

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection
from datetime import datetime


# revision identifiers, used by Alembic.
revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    # Get database connection and inspector
    conn = op.get_bind()
    inspector = reflection.Inspector.from_engine(conn)

    # Drop the categories table if it exists
    if "categories" in inspector.get_table_names():
        op.drop_table("categories")

    # Create categories table
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=False, server_default="EXPENSE"),
        sa.Column(
            "is_system_default", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column(
            "is_auto_generated", sa.Boolean(), nullable=False, server_default="0"
        ),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Insert default categories
    op.execute(
        """
        INSERT INTO categories (name, description, type, is_system_default)
        VALUES 
        ('Income', 'All income transactions', 'INCOME', 1),
        ('Salary', 'Regular employment income', 'INCOME', 1),
        ('Bonus', 'Additional employment compensation', 'INCOME', 1),
        ('Investment Income', 'Income from investments', 'INCOME', 1),
        ('Expenses', 'All expense transactions', 'EXPENSE', 1),
        ('Housing', 'Housing related expenses', 'EXPENSE', 1),
        ('Utilities', 'Utility bills and services', 'EXPENSE', 1),
        ('Transportation', 'Transportation costs', 'EXPENSE', 1),
        ('Food & Dining', 'Food and restaurant expenses', 'EXPENSE', 1),
        ('Shopping', 'General shopping expenses', 'EXPENSE', 1),
        ('Healthcare', 'Medical and healthcare expenses', 'EXPENSE', 1),
        ('Entertainment', 'Entertainment and recreation', 'EXPENSE', 1),
        ('Transfer', 'Money transfers between accounts', 'TRANSFER', 1),
        ('Internal Transfer', 'Transfers between own accounts', 'TRANSFER', 1),
        ('External Transfer', 'Transfers to external accounts', 'TRANSFER', 1)
    """
    )

    # Create new statement_types table with updated schema
    op.create_table(
        "statement_types_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("file_pattern", sa.String(), nullable=True),
        sa.Column("parser_module", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy data from old table to new table
    op.execute(
        """
        INSERT INTO statement_types_new (id, name, description, is_active, created_at, updated_at)
        SELECT id, name, description, is_active, created_at, updated_at
        FROM statement_types
    """
    )

    # Drop old table
    op.drop_table("statement_types")

    # Rename new table to old table name
    op.rename_table("statement_types_new", "statement_types")

    # Insert default statement types with parser information
    op.execute(
        """
        INSERT INTO statement_types (name, description, file_pattern, parser_module, is_active)
        VALUES 
        ('First Republic Bank', 'First Republic Bank statements', '*.pdf', 'first_republic_bank_parser', 1),
        ('Wells Fargo Visa', 'Wells Fargo Visa credit card statements', '*.pdf', 'wellsfargo_visa_parser', 1),
        ('Amazon', 'Amazon order history reports', '*.csv', 'amazon_parser', 1)
    """
    )


def downgrade():
    # Get database connection and inspector
    conn = op.get_bind()
    inspector = reflection.Inspector.from_engine(conn)

    # Drop the categories table if it exists
    if "categories" in inspector.get_table_names():
        op.drop_table("categories")

    # Create new statement_types table without parser columns
    op.create_table(
        "statement_types_new",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Copy data from old table to new table
    op.execute(
        """
        INSERT INTO statement_types_new (id, name, description, is_active, created_at, updated_at)
        SELECT id, name, description, is_active, created_at, updated_at
        FROM statement_types
    """
    )

    # Drop old table
    op.drop_table("statement_types")

    # Rename new table to old table name
    op.rename_table("statement_types_new", "statement_types")
