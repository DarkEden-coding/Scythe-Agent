"""Memory management package: pluggable context-compression strategies."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MemoryConfig:
    """Runtime configuration for the active memory strategy."""

    mode: str = "observational"
    observer_model: str | None = None
    reflector_model: str | None = None
    observer_threshold: int = 30000
    buffer_tokens: int = 6000
    reflector_threshold: int = 8000
    show_observations_in_chat: bool = False

    @classmethod
    def from_settings_repo(cls, settings_repo) -> "MemoryConfig":
        """Load memory config from the settings repository."""
        mem = settings_repo.get_memory_settings()
        return cls(
            mode=mem.get("memory_mode", "observational"),
            observer_model=mem.get("observer_model"),
            reflector_model=mem.get("reflector_model"),
            observer_threshold=mem.get("observer_threshold", 30000),
            buffer_tokens=mem.get("buffer_tokens", 6000),
            reflector_threshold=mem.get("reflector_threshold", 8000),
            show_observations_in_chat=mem.get("show_observations_in_chat", False),
        )


__all__ = ["MemoryConfig"]
