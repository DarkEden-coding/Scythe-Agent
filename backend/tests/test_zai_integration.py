import asyncio

from app.db.session import get_sessionmaker
from app.providers.zai.model_catalog import (
    ZAI_FALLBACK_MODELS,
    ZAiModelCatalogService,
)


def _zai_models() -> list[str]:
    with get_sessionmaker()() as session:
        rows = ZAiModelCatalogService(session).repo.list_models()
        return sorted([r.label for r in rows if r.provider == "zai"])


def test_zai_model_catalog_augments_glm_4_7_flash_when_missing_from_api() -> None:
    class _Client:
        async def get_models(self) -> list[dict]:
            return [
                {"id": "glm-4.7", "context_length": 128000},
                {"id": "glm-4.7", "context_length": 1},
                {"id": ""},
                {"name": "missing-id"},
            ]

    with get_sessionmaker()() as session:
        service = ZAiModelCatalogService(session, client=_Client())  # type: ignore[arg-type]
        service.repo.replace_models_for_provider("zai", [])
        service.repo.commit()

        available = asyncio.run(service.sync_models_on_startup(force_refresh=True))
        assert "glm-4.7" in available
        assert "glm-4.7-flash" in available

        cached = [m for m in service.repo.list_models() if m.provider == "zai"]
        cached_by_label = {m.label: m for m in cached}
        assert "glm-4.7-flash" in cached_by_label
        assert cached_by_label["glm-4.7-flash"].context_limit == service.app_settings.default_context_limit


def test_zai_model_catalog_fetch_failure_keeps_cache_and_adds_manual_flash() -> None:
    class _ClientFail:
        async def get_models(self) -> list[dict]:
            raise RuntimeError("provider unavailable")

    with get_sessionmaker()() as session:
        service = ZAiModelCatalogService(session, client=_ClientFail())  # type: ignore[arg-type]
        seeded = service._normalize(  # noqa: SLF001 - test setup
            [{"id": "cached-zai-model", "context_length": 4096}],
            service._now(),  # noqa: SLF001 - test setup
        )
        service.repo.replace_models_for_provider("zai", seeded)
        service.repo.commit()

        available = asyncio.run(service.sync_models_on_startup(force_refresh=True))
        assert "cached-zai-model" in available
        assert "glm-4.7-flash" in available
        assert set(_zai_models()) == {"cached-zai-model", "glm-4.7-flash"}


def test_zai_model_catalog_fetch_failure_without_cache_uses_fallback_with_flash() -> None:
    class _ClientFail:
        async def get_models(self) -> list[dict]:
            raise RuntimeError("provider unavailable")

    with get_sessionmaker()() as session:
        service = ZAiModelCatalogService(session, client=_ClientFail())  # type: ignore[arg-type]
        service.repo.replace_models_for_provider("zai", [])
        service.repo.commit()

        available = asyncio.run(service.sync_models_on_startup(force_refresh=True))
        assert set(available) == set(ZAI_FALLBACK_MODELS)
        assert "glm-4.7-flash" in available
