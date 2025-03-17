"""add statement types

Revision ID: 002
Revises: 001
Create Date: 2024-03-17 20:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    # Create statement_types table
    op.create_table(
        "statement_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["clients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_statement_types_id"), "statement_types", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_statement_types_name"), "statement_types", ["name"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_statement_types_name"), table_name="statement_types")
    op.drop_index(op.f("ix_statement_types_id"), table_name="statement_types")
    op.drop_table("statement_types")
