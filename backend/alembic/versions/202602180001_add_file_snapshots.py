"""add file_snapshots table

Revision ID: 202602180001
Revises: 202602160001
Create Date: 2026-02-18
"""

from alembic import op
import sqlalchemy as sa

revision = "202602180001"
down_revision = "202602160001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_snapshots",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("file_edit_id", sa.Text(), nullable=True),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["checkpoints.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["file_edit_id"], ["file_edits.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("file_snapshots")
