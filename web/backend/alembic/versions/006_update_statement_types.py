"""update statement types

Revision ID: 006
Revises: 005
Create Date: 2024-03-21

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection
from datetime import datetime


# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
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

    # Create client_statement_types table
    op.create_table(
        "client_statement_types",
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("statement_type_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.ForeignKeyConstraint(
            ["statement_type_id"],
            ["statement_types_new.id"],
        ),
        sa.PrimaryKeyConstraint("client_id", "statement_type_id"),
    )

    # Drop old table immediately (no need to copy data since we're replacing everything)
    op.drop_table("statement_types")

    # Rename new table to old table name
    op.rename_table("statement_types_new", "statement_types")

    # Insert default statement types with parser information
    op.execute(
        """
        INSERT INTO statement_types (name, description, file_pattern, parser_module, is_active)
        VALUES 
        ('First Republic Bank', 'First Republic Bank statements', '*.pdf', 'first_republic_bank_parser', 1),
        ('Wells Fargo Bank', 'Wells Fargo bank statements', '*.pdf', 'wellsfargo_bank_parser', 1),
        ('Wells Fargo Mastercard', 'Wells Fargo Mastercard credit card statements', '*.pdf', 'wellsfargo_mastercard_parser', 1),
        ('Wells Fargo Visa', 'Wells Fargo Visa credit card statements', '*.pdf', 'wellsfargo_visa_parser', 1),
        ('Bank of America Bank', 'Bank of America bank statements', '*.pdf', 'bofa_bank_parser', 1),
        ('Bank of America Visa', 'Bank of America credit card statements', '*.pdf', 'bofa_visa_parser', 1),
        ('Chase Visa', 'Chase credit card statements', '*.pdf', 'chase_visa_parser', 1),
        ('Amazon', 'Amazon order history reports', '*.csv', 'amazon_parser', 1)
    """
    )


def downgrade():
    # Create old statement_types table
    op.create_table(
        "statement_types_old",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Drop new tables
    op.drop_table("client_statement_types")
    op.drop_table("statement_types")

    # Rename old table to statement_types
    op.rename_table("statement_types_old", "statement_types")
