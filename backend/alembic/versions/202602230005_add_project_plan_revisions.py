"""add project_plan_revisions table

Revision ID: 202602230005
Revises: 202602230004
Create Date: 2026-02-23
"""

from alembic import op
import sqlalchemy as sa

revision = "202602230005"
down_revision = "202602230004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_plan_revisions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("plan_id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("last_editor", sa.Text(), nullable=False),
        sa.Column("approved_action", sa.Text(), nullable=True),
        sa.Column("implementation_chat_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["project_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["checkpoint_id"], ["checkpoints.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_plan_revisions_plan_revision",
        "project_plan_revisions",
        ["plan_id", "revision"],
        unique=True,
    )
    op.create_index(
        "ix_project_plan_revisions_plan_created",
        "project_plan_revisions",
        ["plan_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_project_plan_revisions_plan_created", table_name="project_plan_revisions")
    op.drop_index("ix_project_plan_revisions_plan_revision", table_name="project_plan_revisions")
    op.drop_table("project_plan_revisions")
