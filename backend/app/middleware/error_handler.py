from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.api.envelope import err

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Raise from the service layer for known user-facing errors."""

    pass


async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=err(str(exc)).model_dump(),
    )


async def catch_all_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error in %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=err("Internal server error").model_dump(),
    )
