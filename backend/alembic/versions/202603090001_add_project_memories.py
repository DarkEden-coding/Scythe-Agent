"""add project memories table

Revision ID: 202603090001
Revises: 202603020001
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa

revision = "202603090001"
down_revision = "202603020001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_memories",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "title", name="uq_project_memories_project_title"),
    )
    op.create_index("ix_project_memories_project_id", "project_memories", ["project_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_project_memories_project_id", table_name="project_memories")
    op.drop_table("project_memories")
