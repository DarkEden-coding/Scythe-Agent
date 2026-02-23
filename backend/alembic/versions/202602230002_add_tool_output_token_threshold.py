"""add tool_output_token_threshold to settings (fix for DBs stamped 202602230002)

Revision ID: 202602230002
Revises: 202602230001
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa

revision = "202602230002"
down_revision = "202602230001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add tool_output_token_threshold if missing (some DBs have tool_output_spill_threshold instead)
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        cursor = conn.execute(sa.text("PRAGMA table_info(settings)"))
        cols = [row[1] for row in cursor]
        if "tool_output_token_threshold" not in cols:
            op.add_column(
                "settings",
                sa.Column("tool_output_token_threshold", sa.Integer(), nullable=True),
            )
            op.execute(
                sa.text(
                    "UPDATE settings SET tool_output_token_threshold = 2000 "
                    "WHERE tool_output_token_threshold IS NULL"
                )
            )
    else:
        op.add_column(
            "settings",
            sa.Column("tool_output_token_threshold", sa.Integer(), nullable=True),
        )
        op.execute(
            sa.text(
                "UPDATE settings SET tool_output_token_threshold = 2000 "
                "WHERE tool_output_token_threshold IS NULL"
            )
        )


def downgrade() -> None:
    op.drop_column("settings", "tool_output_token_threshold")
