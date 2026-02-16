from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

from app.utils.time import utc_now_iso

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    ok: bool
    data: T | None
    error: str | None = None
    timestamp: str


def ok(data: T) -> ApiResponse[T]:
    return ApiResponse(ok=True, data=data, timestamp=utc_now_iso())


def err(message: str) -> ApiResponse[None]:
    return ApiResponse(ok=False, data=None, error=message, timestamp=utc_now_iso())

