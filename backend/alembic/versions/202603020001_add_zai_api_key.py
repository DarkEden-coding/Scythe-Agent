"""add zai api key to settings

Revision ID: 202603020001
Revises: 202602260003
Create Date: 2026-03-02

"""

from alembic import op
import sqlalchemy as sa

revision = "202603020001"
down_revision = "202602260003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("zai_api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "zai_api_key")
