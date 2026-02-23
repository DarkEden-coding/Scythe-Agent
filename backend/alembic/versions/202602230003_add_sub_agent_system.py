"""Add sub-agent system: sub_agent_runs table and settings columns.

Revision ID: 202602230003
Revises: 202602230002
Create Date: 2026-02-23

"""

from alembic import op
import sqlalchemy as sa

revision = "202602230003"
down_revision = "202602230002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sub_agent_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("tool_call_id", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("timestamp", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_call_id"], ["tool_calls.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column(
        "settings",
        sa.Column("sub_agent_model", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("sub_agent_model_provider", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("sub_agent_model_key", sa.Text(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("max_parallel_sub_agents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "settings",
        sa.Column("sub_agent_max_iterations", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE settings SET max_parallel_sub_agents = 4 WHERE max_parallel_sub_agents IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE settings SET sub_agent_max_iterations = 25 WHERE sub_agent_max_iterations IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_table("sub_agent_runs")
    op.drop_column("settings", "sub_agent_max_iterations")
    op.drop_column("settings", "max_parallel_sub_agents")
    op.drop_column("settings", "sub_agent_model_key")
    op.drop_column("settings", "sub_agent_model_provider")
    op.drop_column("settings", "sub_agent_model")
