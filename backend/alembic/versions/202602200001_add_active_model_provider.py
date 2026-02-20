"""add active_model_provider to settings

Revision ID: 202602200001
Revises: 202602190005
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "202602200001"
down_revision = "202602190005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("settings")}
    if "active_model_provider" not in cols:
        op.add_column("settings", sa.Column("active_model_provider", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {c["name"] for c in inspector.get_columns("settings")}
    if "active_model_provider" in cols:
        op.drop_column("settings", "active_model_provider")
