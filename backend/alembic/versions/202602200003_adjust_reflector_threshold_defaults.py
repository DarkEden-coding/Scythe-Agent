"""adjust reflector threshold defaults for observational memory

Revision ID: 202602200003
Revises: 202602200002
Create Date: 2026-02-20
"""

from alembic import op
import sqlalchemy as sa

revision = "202602200003"
down_revision = "202602200002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    if dialect != "sqlite":
        op.alter_column(
            "settings",
            "reflector_threshold",
            existing_type=sa.Integer(),
            server_default="8000",
            existing_nullable=True,
        )
    # Migrate legacy default values to a reachable threshold.
    op.execute(
        sa.text(
            "UPDATE settings SET reflector_threshold = 8000 "
            "WHERE reflector_threshold IS NULL OR reflector_threshold = 40000"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name if bind is not None else ""
    if dialect != "sqlite":
        op.alter_column(
            "settings",
            "reflector_threshold",
            existing_type=sa.Integer(),
            server_default="40000",
            existing_nullable=True,
        )
    op.execute(
        sa.text(
            "UPDATE settings SET reflector_threshold = 40000 "
            "WHERE reflector_threshold IS NULL OR reflector_threshold = 8000"
        )
    )
