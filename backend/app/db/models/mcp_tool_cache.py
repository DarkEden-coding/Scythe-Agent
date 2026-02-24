from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MCPToolCache(Base):
    __tablename__ = "mcp_tools_cache"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    server_id: Mapped[str] = mapped_column(ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    schema_json: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    discovered_at: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

