"""add todos table

Revision ID: 202602190002
Revises: 202602190001
Create Date: 2026-02-19

"""

from alembic import op
import sqlalchemy as sa

revision = "202602190002"
down_revision = "202602190001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "todos",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("todos")
