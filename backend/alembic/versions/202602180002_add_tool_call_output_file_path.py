"""add output_file_path to tool_calls

Revision ID: 202602180002
Revises: 202602180001
Create Date: 2026-02-18

"""

from alembic import op
import sqlalchemy as sa

revision = "202602180002"
down_revision = "202602180001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tool_calls",
        sa.Column("output_file_path", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tool_calls", "output_file_path")
