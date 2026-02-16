from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.api.envelope import err, ok
from app.services.filesystem_service import FilesystemService

router = APIRouter(prefix="/api/fs", tags=["filesystem"])


@router.get("/children")
def get_children(path: str | None = Query(default=None)):
    try:
        data = FilesystemService().get_children(path)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())
