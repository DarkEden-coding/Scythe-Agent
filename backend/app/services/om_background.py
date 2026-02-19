"""Re-export shim — logic lives in app.services.memory.observational.background."""

from app.services.memory.observational.background import OMBackgroundRunner, om_runner

__all__ = ["OMBackgroundRunner", "om_runner"]
