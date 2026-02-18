"""add system_prompt to settings

Revision ID: 202602180003
Revises: 202602180002
Create Date: 2026-02-18

"""

from alembic import op
import sqlalchemy as sa

revision = "202602180003"
down_revision = "202602180002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("system_prompt", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "system_prompt")
