"""Re-export shim — logic lives in app.services.memory.observational.service."""

from app.services.memory.observational.service import ObservationMemoryService

__all__ = ["ObservationMemoryService"]
