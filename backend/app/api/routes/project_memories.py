from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.middleware.error_handler import full_error_message
from app.schemas.projects import UpsertProjectMemoryRequest
from app.services.project_memory_service import ProjectMemoryService

router = APIRouter(tags=["project-memories"])


@router.get("/api/projects/{project_id}/memories")
def list_project_memories(project_id: str, db: Session = Depends(get_db)):
    try:
        data = ProjectMemoryService(db).list_project_memories(project_id=project_id)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.post("/api/projects/{project_id}/memories")
def upsert_project_memory(
    project_id: str,
    request: UpsertProjectMemoryRequest,
    db: Session = Depends(get_db),
):
    try:
        data = ProjectMemoryService(db).write_memory_from_request(
            project_id=project_id,
            request=request,
        )
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.delete("/api/projects/{project_id}/memories/{title}")
def delete_project_memory(project_id: str, title: str, db: Session = Depends(get_db)):
    try:
        data = ProjectMemoryService(db).delete_project_memory(project_id=project_id, title=title)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())
