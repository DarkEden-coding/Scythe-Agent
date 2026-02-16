from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.envelope import err, ok
from app.schemas.settings import SetAutoApproveRequest, SetModelRequest
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).get_settings()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


@router.get("/auto-approve")
def get_auto_approve(db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).get_auto_approve_rules()
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


@router.put("/auto-approve")
def set_auto_approve(request: SetAutoApproveRequest, db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).set_auto_approve_rules(request.rules)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())


@router.put("/model")
def set_model(request: SetModelRequest, db: Session = Depends(get_db)):
    try:
        data = SettingsService(db).set_model(request.model)
        return ok(data.model_dump())
    except ValueError as exc:
        return JSONResponse(status_code=400, content=err(str(exc)).model_dump())
    except Exception:
        return JSONResponse(status_code=500, content=err("Internal server error").model_dump())
