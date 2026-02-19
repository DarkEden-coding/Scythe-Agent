"""Re-export shim — logic lives in app.services.memory.observational.prompts."""

from app.services.memory.observational.prompts import (
    build_observer_prompt,
    build_reflector_prompt,
    parse_observation_output,
)

__all__ = [
    "build_observer_prompt",
    "build_reflector_prompt",
    "parse_observation_output",
]
