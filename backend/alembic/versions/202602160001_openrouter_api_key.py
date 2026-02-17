"""add openrouter api key to settings

Revision ID: 202602160001
Revises: 202602060003
Create Date: 2026-02-16
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602160001"
down_revision = "202602060003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add OpenRouter API key and base URL to settings table."""
    op.add_column("settings", sa.Column("openrouter_api_key", sa.Text(), nullable=True))
    op.add_column(
        "settings",
        sa.Column(
            "openrouter_base_url",
            sa.Text(),
            nullable=True,
            server_default="https://openrouter.ai/api/v1"
        )
    )


def downgrade() -> None:
    """Remove OpenRouter API key and base URL from settings table."""
    op.drop_column("settings", "openrouter_base_url")
    op.drop_column("settings", "openrouter_api_key")
