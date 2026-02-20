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
    with op.batch_alter_table("todos") as batch_op:
        batch_op.add_column(sa.Column("checkpoint_id", sa.Text(), nullable=True))
        batch_op.create_foreign_key(
            "fk_todos_checkpoint_id_checkpoints",
            "checkpoints",
            ["checkpoint_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("todos") as batch_op:
        batch_op.drop_constraint("fk_todos_checkpoint_id_checkpoints", type_="foreignkey")
        batch_op.drop_column("checkpoint_id")
