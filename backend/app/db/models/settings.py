from typing import Optional

from sqlalchemy import Integer, Text  # type: ignore
from sqlalchemy.orm import Mapped, mapped_column  # type: ignore

from app.db.base import Base


class Settings(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active_model: Mapped[str] = mapped_column(Text, nullable=False)
    active_model_provider: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    context_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    openrouter_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    openrouter_base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    groq_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    zai_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brave_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    openai_sub_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    openai_sub_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reasoning_level: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default="medium"
    )
    # Observational Memory settings
    memory_mode: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, default="observational"
    )
    observer_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reflector_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observer_threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=30000)
    buffer_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=6000)
    reflector_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=8000
    )
    show_observations_in_chat: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0
    )
    tool_output_token_threshold: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    tool_output_preview_tokens: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    sub_agent_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sub_agent_model_provider: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sub_agent_model_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_parallel_sub_agents: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=4
    )
    sub_agent_max_iterations: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=25
    )
    vision_preprocessor_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vision_preprocessor_model_provider: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    vision_preprocessor_model_key: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
