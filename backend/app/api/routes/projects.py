from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.middleware.error_handler import full_error_message
from app.schemas.projects import (
    CreateChatRequest,
    CreateProjectRequest,
    ReorderChatsRequest,
    ReorderProjectsRequest,
    UpdateChatRequest,
    UpdateProjectRequest,
)
from app.services.project_service import ProjectService

router = APIRouter(tags=["projects"])


@router.get("/api/projects")
def get_projects(db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).get_projects()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.post("/api/projects")
def create_project(request: CreateProjectRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).create_project(name=request.name, path=request.path)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


# Static "/reorder" path must be registered BEFORE the dynamic "/{project_id}" path
# to prevent "reorder" from being captured as a project_id.
@router.patch("/api/projects/reorder")
def reorder_projects(request: ReorderProjectsRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).reorder_projects(project_ids=request.projectIds)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.patch("/api/projects/{project_id}")
def update_project(project_id: str, request: UpdateProjectRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).update_project(project_id=project_id, name=request.name, path=request.path)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).delete_project(project_id=project_id)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


# Static "/chats/reorder" path must be registered BEFORE any route that could
# conflict with it under the same prefix.
@router.patch("/api/projects/{project_id}/chats/reorder")
def reorder_chats(project_id: str, request: ReorderChatsRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).reorder_chats(project_id=project_id, chat_ids=request.chatIds)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.post("/api/projects/{project_id}/chats")
def create_chat(project_id: str, request: CreateChatRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).create_chat(project_id=project_id, title=request.title)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.patch("/api/chats/{chat_id}")
def update_chat(chat_id: str, request: UpdateChatRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).update_chat(chat_id=chat_id, title=request.title, is_pinned=request.isPinned)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())


@router.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).delete_chat(chat_id=chat_id)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(full_error_message(exc)).model_dump())
