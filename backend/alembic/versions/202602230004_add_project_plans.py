"""add project_plans table

Revision ID: 202602230004
Revises: 202602230003
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa

revision = "202602230004"
down_revision = "202602230003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_plans",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("last_editor", sa.Text(), nullable=False),
        sa.Column("approved_action", sa.Text(), nullable=True),
        sa.Column("implementation_chat_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["checkpoints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("project_plans")
