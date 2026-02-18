from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.schemas.chat import (
    ApproveCommandRequest,
    EditMessageRequest,
    RejectCommandRequest,
    SendMessageRequest,
)
from app.services.approval_service import ApprovalService
from app.services.approval_waiter import signal_approved, signal_rejected
from app.services.chat_service import ChatService
from app.services.revert_service import RevertService
from app.services.summarize_service import SummarizeService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.get("/{chat_id}/history")
def get_chat_history(chat_id: str, db: Session = Depends(get_db)):
    try:
        data = ChatService(db).get_chat_history(chat_id)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.get("/{chat_id}/debug")
def get_chat_debug(chat_id: str, db: Session = Depends(get_db)):
    try:
        data = ChatService(db).get_chat_debug(chat_id)
        return ok(data)
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: str, request: SendMessageRequest, db: Session = Depends(get_db)
):
    try:
        data = await ChatService(db).send_message(
            chat_id=chat_id, content=request.content
        )
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.put("/{chat_id}/messages/{message_id}")
async def edit_message(
    chat_id: str, message_id: str, request: EditMessageRequest, db: Session = Depends(get_db)
):
    try:
        data = await ChatService(db).edit_message(
            chat_id=chat_id, message_id=message_id, content=request.content
        )
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.post("/{chat_id}/cancel")
async def cancel_agent(chat_id: str, db: Session = Depends(get_db)):
    """Cancel the running agent for this chat (e.g. when user stops the stream)."""
    try:
        cancelled = await ChatService(db).cancel_agent(chat_id)
        return ok({"cancelled": cancelled})
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.post("/{chat_id}/approve")
async def approve(
    chat_id: str, request: ApproveCommandRequest, db: Session = Depends(get_db)
):
    try:
        tool_call, file_edits = await ApprovalService(db).approve(
            chat_id=chat_id, tool_call_id=request.toolCallId
        )
        signal_approved(chat_id, request.toolCallId)
        return ok(
            {
                "toolCall": tool_call.model_dump(),
                "fileEdits": [f.model_dump() for f in file_edits],
            }
        )
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.post("/{chat_id}/reject")
async def reject(
    chat_id: str, request: RejectCommandRequest, db: Session = Depends(get_db)
):
    try:
        tool_call = await ApprovalService(db).reject(
            chat_id=chat_id,
            tool_call_id=request.toolCallId,
            reason=request.reason,
        )
        signal_rejected(chat_id, request.toolCallId)
        return ok({"toolCallId": tool_call.id, "status": "rejected"})
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.post("/{chat_id}/summarize")
async def summarize(chat_id: str, db: Session = Depends(get_db)):
    try:
        data = await SummarizeService(db).summarize(chat_id)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.post("/{chat_id}/revert/{checkpoint_id}")
def revert(chat_id: str, checkpoint_id: str, db: Session = Depends(get_db)):
    try:
        data = RevertService(db).revert_to_checkpoint(chat_id, checkpoint_id)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )


@router.post("/{chat_id}/revert-file/{file_edit_id}")
def revert_file(chat_id: str, file_edit_id: str, db: Session = Depends(get_db)):
    try:
        data = RevertService(db).revert_file(chat_id, file_edit_id)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(
            status_code=500, content=err("Internal server error").model_dump()
        )
