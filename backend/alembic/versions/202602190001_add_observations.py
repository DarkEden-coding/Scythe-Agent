"""add observations table and memory settings columns

Revision ID: 202602190001
Revises: 202602180006
Create Date: 2026-02-19
"""

from alembic import op
import sqlalchemy as sa

revision = "202602190001"
down_revision = "202602180006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observations",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observed_up_to_message_id", sa.Text(), nullable=True),
        sa.Column("current_task", sa.Text(), nullable=True),
        sa.Column("suggested_response", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "settings",
        sa.Column("memory_mode", sa.Text(), nullable=True, server_default="observational"),
    )
    op.add_column(
        "settings",
        sa.Column("observer_model", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("reflector_model", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("observer_threshold", sa.Integer(), nullable=True, server_default="30000"),
    )
    op.add_column(
        "settings",
        sa.Column("reflector_threshold", sa.Integer(), nullable=True, server_default="40000"),
    )
    op.add_column(
        "settings",
        sa.Column(
            "show_observations_in_chat", sa.Integer(), nullable=True, server_default="0"
        ),
    )


def downgrade() -> None:
    op.drop_column("settings", "show_observations_in_chat")
    op.drop_column("settings", "reflector_threshold")
    op.drop_column("settings", "observer_threshold")
    op.drop_column("settings", "reflector_model")
    op.drop_column("settings", "observer_model")
    op.drop_column("settings", "memory_mode")
    op.drop_table("observations")
