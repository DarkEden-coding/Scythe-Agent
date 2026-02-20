"""add trigger_token_count to observations

Revision ID: 202602200005
Revises: 202602200004
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "202602200005"
down_revision = "202602200004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "observations",
        sa.Column("trigger_token_count", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE observations "
            "SET trigger_token_count = token_count "
            "WHERE trigger_token_count IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("observations", "trigger_token_count")
