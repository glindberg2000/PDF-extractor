"""add file tags

Revision ID: add_file_tags
Revises: cc199066cf64
Create Date: 2024-03-18 11:44:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "add_file_tags"
down_revision = "cc199066cf64"
branch_labels = None
depends_on = None


def upgrade():
    # Add tags column to client_files table
    op.add_column("client_files", sa.Column("tags", sa.JSON(), nullable=True))


def downgrade():
    # Remove tags column from client_files table
    op.drop_column("client_files", "tags")
