"""phase 7 mcp tables

Revision ID: 202602060002
Revises: 202602060001
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "202602060002"
down_revision = "202602060001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "mcp_servers" not in existing:
        op.create_table(
            "mcp_servers",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("name", sa.Text(), nullable=False),
            sa.Column("transport", sa.Text(), nullable=False),
            sa.Column("config_json", sa.Text(), nullable=False),
            sa.Column("enabled", sa.Integer(), nullable=False),
            sa.Column("last_connected_at", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    if "mcp_tools_cache" not in existing:
        op.create_table(
            "mcp_tools_cache",
            sa.Column("id", sa.Text(), nullable=False),
            sa.Column("server_id", sa.Text(), nullable=False),
            sa.Column("tool_name", sa.Text(), nullable=False),
            sa.Column("schema_json", sa.Text(), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("discovered_at", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["server_id"], ["mcp_servers.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())
    if "mcp_tools_cache" in existing:
        op.drop_table("mcp_tools_cache")
    if "mcp_servers" in existing:
        op.drop_table("mcp_servers")

