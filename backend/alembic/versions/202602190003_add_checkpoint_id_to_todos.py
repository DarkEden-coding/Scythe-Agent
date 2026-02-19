"""add checkpoint_id to todos

Revision ID: 202602190003
Revises: 202602190002
Create Date: 2026-02-19

"""

from alembic import op
import sqlalchemy as sa

revision = "202602190003"
down_revision = "202602190002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("todos", sa.Column("checkpoint_id", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_todos_checkpoint_id_checkpoints",
        "todos",
        "checkpoints",
        ["checkpoint_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_todos_checkpoint_id_checkpoints", "todos", type_="foreignkey")
    op.drop_column("todos", "checkpoint_id")
