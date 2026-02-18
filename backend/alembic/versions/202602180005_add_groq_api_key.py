"""add groq api key to settings

Revision ID: 202602180005
Revises: 202602180004
Create Date: 2026-02-18

"""

from alembic import op
import sqlalchemy as sa

revision = "202602180005"
down_revision = "202602180004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("settings", sa.Column("groq_api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("settings", "groq_api_key")
