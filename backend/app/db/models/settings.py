from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active_model: Mapped[str] = mapped_column(Text, nullable=False)
    active_model_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    openrouter_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    openrouter_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    groq_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    openai_sub_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    openai_sub_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_level: Mapped[str | None] = mapped_column(
        Text, nullable=True, default="medium"
    )
    # Observational Memory settings
    memory_mode: Mapped[str | None] = mapped_column(Text, nullable=True, default="observational")
    observer_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    reflector_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    observer_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True, default=30000)
    buffer_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True, default=6000)
    reflector_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True, default=8000)
    show_observations_in_chat: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    tool_output_token_threshold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_output_preview_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sub_agent_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_agent_model_provider: Mapped[str | None] = mapped_column(Text, nullable=True)
    sub_agent_model_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_parallel_sub_agents: Mapped[int | None] = mapped_column(Integer, nullable=True, default=4)
    sub_agent_max_iterations: Mapped[int | None] = mapped_column(Integer, nullable=True, default=25)
