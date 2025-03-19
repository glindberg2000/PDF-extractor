"""update_statement_types_and_files

Revision ID: f43d77c952a3
Revises: f1b3ed9ad7b4
Create Date: 2024-03-19 07:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "f43d77c952a3"
down_revision = "f1b3ed9ad7b4"
branch_labels = None
depends_on = None


def upgrade():
    # Add CHECK constraint for status
    with op.batch_alter_table("client_files") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.String(),
            type_=sa.String(),
            nullable=False,
            server_default="pending",
        )
        batch_op.create_check_constraint(
            "status_types",
            "status IN ('pending', 'processing', 'completed', 'failed', 'archived')",
        )

    # Add indexes for better performance
    op.create_index("ix_client_files_status", "client_files", ["status"])
    op.create_index("ix_client_files_uploaded_at", "client_files", ["uploaded_at"])
    op.create_index("ix_client_files_processed_at", "client_files", ["processed_at"])


def downgrade():
    # Remove indexes
    op.drop_index("ix_client_files_status")
    op.drop_index("ix_client_files_uploaded_at")
    op.drop_index("ix_client_files_processed_at")

    # Remove CHECK constraint
    with op.batch_alter_table("client_files") as batch_op:
        batch_op.drop_constraint("status_types")
        batch_op.alter_column(
            "status", existing_type=sa.String(), type_=sa.String(), nullable=True
        )
