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
uv sync
alembic upgrade head
uv run uvicorn app.main:app --reload --port 3001
```

**Important:** Use `uv run uvicorn` so the process uses the project venv. Running `uvicorn` directly (e.g. from conda or system Python) will miss `tree-sitter-language-pack`, and `get_file_structure` will return "No tree-sitter support" for structure extraction.

To run from the repository root:

```bash
uv run --project backend uvicorn app.main:app --app-dir backend --reload --port 3001
```

## Tests

```bash
cd backend
pytest
```

## Notes

- DB defaults to SQLite file `backend/agentic.db`.
- On startup, the app performs idempotent seed initialization for settings and configuration.
- Domain values stay API-reference aligned (`assistant`, `created/modified/deleted`) and are mapped to UI-compatible response values in serializer utilities.
