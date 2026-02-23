"""add tool_output_token_threshold and tool_output_preview_tokens to settings

Revision ID: 202602230001
Revises: 202602200005
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa

revision = "202602230001"
down_revision = "202602200005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("tool_output_token_threshold", sa.Integer(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("tool_output_preview_tokens", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE settings SET tool_output_token_threshold = 2000 "
            "WHERE tool_output_token_threshold IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE settings SET tool_output_preview_tokens = 500 "
            "WHERE tool_output_preview_tokens IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("settings", "tool_output_token_threshold")
    op.drop_column("settings", "tool_output_preview_tokens")
