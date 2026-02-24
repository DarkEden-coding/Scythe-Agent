"""add brave_api_key to settings

Revision ID: 202602230006
Revises: 202602230005
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa

revision = "202602230006"
down_revision = "202602230005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("brave_api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "brave_api_key")
