from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | None
    error: str | None = None
    timestamp: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ok(data: T) -> ApiResponse[T]:
    return ApiResponse(ok=True, data=data, timestamp=_now_iso())


def err(message: str) -> ApiResponse[None]:
    return ApiResponse(ok=False, data=None, error=message, timestamp=_now_iso())

