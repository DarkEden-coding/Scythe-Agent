import asyncio

from fastapi.testclient import TestClient

from app.db.models.settings import Settings
from app.db.session import get_sessionmaker
from app.main import create_app
from app.providers.openrouter.model_catalog import OpenRouterModelCatalogService


def _available_models() -> list[str]:
    with get_sessionmaker()() as session:
        rows = OpenRouterModelCatalogService(session).repo.list_models()
        return [r.label for r in rows]


def test_model_catalog_fetch_success_writes_cache() -> None:
    class _Client:
        async def get_models(self) -> list[dict]:
            return [
                {"id": "z-model", "context_length": 8192},
                {"id": "a-model", "max_context_tokens": "4096"},
                {"id": "a-model", "context_length": 1000},
                {"id": ""},
                {"name": "missing-id"},
            ]

    with get_sessionmaker()() as session:
        service = OpenRouterModelCatalogService(session, client=_Client())  # type: ignore[arg-type]
        available = asyncio.run(service.sync_models_on_startup())
        assert available == ["a-model", "z-model"]
        cached = service.repo.list_models()
        assert [m.label for m in cached] == ["a-model", "z-model"]
        assert cached[0].context_limit == 4096
        assert cached[1].context_limit == 8192


def test_model_catalog_fetch_failure_uses_cache_then_fallback() -> None:
    class _ClientFail:
        async def get_models(self) -> list[dict]:
            raise RuntimeError("provider unavailable")

    with get_sessionmaker()() as session:
        service = OpenRouterModelCatalogService(session, client=_ClientFail())  # type: ignore[arg-type]
        service.repo.replace_models(service._normalize([{"id": "cached-model", "context_length": 2048}], service._now()))
        service.repo.commit()
        available_cached = asyncio.run(service.sync_models_on_startup())
        assert "cached-model" in available_cached
        assert _available_models() == ["cached-model"]

        service.repo.replace_models([])
        service.repo.commit()
        available_fallback = asyncio.run(service.sync_models_on_startup())
        assert available_fallback
        assert set(available_fallback) == set(service.app_settings.fallback_models)


def test_settings_model_update_validation_and_autocorrect(client) -> None:
    settings_payload = client.get("/api/settings").json()["data"]
    available = settings_payload["availableModels"]
    assert available

    valid_target = available[0]
    valid_res = client.put("/api/settings/model", json={"model": valid_target})
    assert valid_res.status_code == 200
    valid_body = valid_res.json()
    assert valid_body["ok"] is True
    assert valid_body["data"]["model"] == valid_target

    invalid_res = client.put("/api/settings/model", json={"model": "not-a-real-model"})
    assert invalid_res.status_code == 200
    invalid_body = invalid_res.json()
    assert invalid_body["ok"] is False
    assert "not available" in invalid_body["error"]

    with get_sessionmaker()() as session:
        settings_row = session.get(Settings, 1)
        assert settings_row is not None
        settings_row.active_model = "broken-model"
        session.commit()

    corrected = client.get("/api/settings").json()["data"]
    assert corrected["model"] in set(corrected["availableModels"])


def test_startup_resilience_when_provider_unavailable(monkeypatch) -> None:
    async def _fail_models(self):
        raise RuntimeError("network down")

    monkeypatch.setattr("app.providers.openrouter.client.OpenRouterClient.get_models", _fail_models)

    with TestClient(create_app()) as startup_client:
        response = startup_client.get("/api/settings")
        assert response.status_code == 200
        body = response.json()
        assert body["ok"] is True
        assert body["data"]["availableModels"]

