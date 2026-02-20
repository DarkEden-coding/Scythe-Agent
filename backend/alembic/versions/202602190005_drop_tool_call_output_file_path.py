"""drop output_file_path from tool_calls

Revision ID: 202602190005
Revises: 202602190004
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa

revision = "202602190005"
down_revision = "202602190004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("tool_calls")}
    if "output_file_path" in cols:
        op.drop_column("tool_calls", "output_file_path")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("tool_calls")}
    if "output_file_path" not in cols:
        op.add_column("tool_calls", sa.Column("output_file_path", sa.Text(), nullable=True))
