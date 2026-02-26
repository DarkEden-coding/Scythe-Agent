"""Add vision preprocessor settings for summarizing images when main model lacks vision.

Revision ID: 202602260002
Revises: 202602260001
Create Date: 2026-02-26

"""

from alembic import op
import sqlalchemy as sa

revision = "202602260002"
down_revision = "202602260001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "settings",
        sa.Column("vision_preprocessor_model", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("vision_preprocessor_model_provider", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("vision_preprocessor_model_key", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("settings", "vision_preprocessor_model_key")
    op.drop_column("settings", "vision_preprocessor_model_provider")
    op.drop_column("settings", "vision_preprocessor_model")
