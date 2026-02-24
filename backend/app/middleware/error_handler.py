from __future__ import annotations

import logging
import traceback

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.envelope import err

logger = logging.getLogger(__name__)


def _format_validation_error(exc: RequestValidationError) -> str:
    """Turn Pydantic validation errors into a readable message."""
    parts = []
    for err_entry in exc.errors():
        loc = err_entry.get("loc", ())
        loc_str = ".".join(str(x) for x in loc if x != "body")
        msg = err_entry.get("msg", "Validation error")
        parts.append(f"{loc_str}: {msg}" if loc_str else msg)
    return "; ".join(parts) or "Request validation failed"


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return 422 validation errors in the app envelope format with a readable message."""
    message = _format_validation_error(exc)
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, message)
    return JSONResponse(
        status_code=422,
        content=err(message).model_dump(),
    )


class ServiceError(Exception):
    """Raise from the service layer for known user-facing errors."""

    pass


def full_error_message(exc: Exception) -> str:
    """Return full exception details including traceback."""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).strip()


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=err(str(exc)).model_dump(),
    )


async def catch_all_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=err(full_error_message(exc)).model_dump(),
    )
