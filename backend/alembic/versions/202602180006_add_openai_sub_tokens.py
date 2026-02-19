"""add openai subscription oauth tokens to settings

Revision ID: 202602180006
Revises: 202602180005
Create Date: 2026-02-18

"""

from alembic import op
import sqlalchemy as sa

revision = "202602180006"
down_revision = "202602180005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("openai_sub_access_token", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("openai_sub_refresh_token", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("settings", "openai_sub_refresh_token")
    op.drop_column("settings", "openai_sub_access_token")
