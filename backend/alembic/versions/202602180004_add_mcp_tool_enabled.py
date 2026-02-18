"""add enabled to mcp_tools_cache

Revision ID: 202602180004
Revises: 202602180003
Create Date: 2026-02-18

"""

from alembic import op
import sqlalchemy as sa

revision = "202602180004"
down_revision = "202602180003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "mcp_tools_cache",
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("mcp_tools_cache", "enabled")
