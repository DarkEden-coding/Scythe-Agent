"""add reasoning_level setting

Revision ID: 202602200004
Revises: 202602200003
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "202602200004"
down_revision = "202602200003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("settings")}
    if "reasoning_level" not in cols:
        op.add_column(
            "settings",
            sa.Column(
                "reasoning_level",
                sa.Text(),
                nullable=True,
                server_default="medium",
            ),
        )
    op.execute(
        sa.text(
            "UPDATE settings SET reasoning_level = 'medium' "
            "WHERE reasoning_level IS NULL OR TRIM(reasoning_level) = ''"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("settings")}
    if "reasoning_level" in cols:
        op.drop_column("settings", "reasoning_level")
