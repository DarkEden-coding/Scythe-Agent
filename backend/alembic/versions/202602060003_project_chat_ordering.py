"""add project/chat ordering and pinning

Revision ID: 202602060003
Revises: 202602060002
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602060003"
down_revision = "202602060002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("chats", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("chats", sa.Column("is_pinned", sa.Integer(), nullable=False, server_default="0"))
    bind = op.get_bind()
    project_rows = bind.execute(sa.text("SELECT id FROM projects ORDER BY last_active DESC, id ASC")).fetchall()
    for idx, row in enumerate(project_rows):
        bind.execute(sa.text("UPDATE projects SET sort_order=:sort_order WHERE id=:id"), {"sort_order": idx, "id": row[0]})

    chat_rows = bind.execute(
        sa.text("SELECT id, project_id FROM chats ORDER BY project_id ASC, updated_at DESC, id ASC")
    ).fetchall()
    chat_order: dict[str, int] = {}
    for row in chat_rows:
        project_id = row[1]
        current = chat_order.get(project_id, 0)
        bind.execute(
            sa.text("UPDATE chats SET sort_order=:sort_order WHERE id=:id"),
            {"sort_order": current, "id": row[0]},
        )
        chat_order[project_id] = current + 1


def downgrade() -> None:
    op.drop_column("chats", "is_pinned")
    op.drop_column("chats", "sort_order")
    op.drop_column("projects", "sort_order")
