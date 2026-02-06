from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
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
    except Exception as exc:  # pragma: no cover - defensive route boundary
        return err(str(exc))


@router.post("/api/projects")
def create_project(request: CreateProjectRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).create_project(name=request.name, path=request.path)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))


@router.patch("/api/projects/{project_id}")
def update_project(project_id: str, request: UpdateProjectRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).update_project(project_id=project_id, name=request.name, path=request.path)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))


@router.delete("/api/projects/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).delete_project(project_id=project_id)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))


@router.patch("/api/projects/reorder")
def reorder_projects(request: ReorderProjectsRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).reorder_projects(project_ids=request.projectIds)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))


@router.post("/api/projects/{project_id}/chats")
def create_chat(project_id: str, request: CreateChatRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).create_chat(project_id=project_id, title=request.title)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))


@router.patch("/api/chats/{chat_id}")
def update_chat(chat_id: str, request: UpdateChatRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).update_chat(chat_id=chat_id, title=request.title, is_pinned=request.isPinned)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))


@router.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).delete_chat(chat_id=chat_id)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))


@router.patch("/api/projects/{project_id}/chats/reorder")
def reorder_chats(project_id: str, request: ReorderChatsRequest, db: Session = Depends(get_db)):
    try:
        data = ProjectService(db).reorder_chats(project_id=project_id, chat_ids=request.chatIds)
        return ok(data.model_dump())
    except Exception as exc:  # pragma: no cover
        return err(str(exc))
