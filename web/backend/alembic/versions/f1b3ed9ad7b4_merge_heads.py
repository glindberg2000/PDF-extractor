"""merge_heads

Revision ID: f1b3ed9ad7b4
Revises: 006, add_file_tags
Create Date: 2025-03-18 23:56:15.642584

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1b3ed9ad7b4'
down_revision = ('006', 'add_file_tags')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass 