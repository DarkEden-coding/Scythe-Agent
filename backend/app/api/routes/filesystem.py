from fastapi import APIRouter, Query

from app.api.envelope import err, ok
from app.services.filesystem_service import FilesystemService

router = APIRouter(prefix="/api/fs", tags=["filesystem"])


@router.get("/children")
def get_children(path: str | None = Query(default=None)):
    try:
        data = FilesystemService().get_children(path)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover - defensive route boundary
        return err(str(exc))
