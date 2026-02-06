# Backend MVP (Phase 0-2)

This backend implements the scoped MVP from [`plans/backend-python-mvp-plan.md`](../plans/backend-python-mvp-plan.md) for:

- [`GET /api/projects`](app/api/routes/projects.py)
- [`GET /api/settings`](app/api/routes/settings.py)
- [`GET /api/chat/{chatId}/history`](app/api/routes/chat.py)

## Stack

- FastAPI
- Pydantic v2
- SQLAlchemy 2
- Alembic
- httpx
- pytest

## Quick start

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 3001
```

If you run from the repository root instead of `backend/`, use:

```bash
python3 -m uvicorn app.main:app --app-dir backend --reload --port 3001
```

## Tests

```bash
cd backend
pytest
```

## Notes

- DB defaults to SQLite file `backend/agentic.db`.
- On startup, the app performs idempotent seed initialization for demo data.
- Domain values stay API-reference aligned (`assistant`, `created/modified/deleted`) and are mapped to UI-compatible response values in serializer utilities.
