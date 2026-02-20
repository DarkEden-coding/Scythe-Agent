"""add buffer_tokens memory setting

Revision ID: 202602200002
Revises: 202602200001
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "202602200002"
down_revision = "202602200001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("buffer_tokens", sa.Integer(), nullable=True, server_default="6000"),
    )


def downgrade() -> None:
    op.drop_column("settings", "buffer_tokens")
