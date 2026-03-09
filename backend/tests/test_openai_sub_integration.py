import asyncio
import json

from app.db.session import get_sessionmaker
from app.providers.openai_sub.model_catalog import OpenAISubModelCatalogService


def test_openai_sub_model_catalog_uses_local_schema_metadata() -> None:
    with get_sessionmaker()() as session:
        service = OpenAISubModelCatalogService(session, client=None)
        service.repo.replace_models_for_provider("openai-sub", [])
        service.repo.commit()

        available = asyncio.run(service.sync_models_on_startup(force_refresh=True))
        assert "gpt-5.3-codex-spark" in available

        cached = [m for m in service.repo.list_models() if m.provider == "openai-sub"]
        cached_by_label = {m.label: m for m in cached}
        assert cached_by_label["gpt-5.3-codex-spark"].context_limit == 128_000

        raw = json.loads(cached_by_label["gpt-5.3-codex-spark"].raw_json)
        assert raw["description"] == "GPT-5.3 Codex Spark: Fast, text-only coding model via ChatGPT subscription"
        assert raw["supportsImages"] is False
        assert raw["supportsReasoningEffort"] == ["low", "medium", "high", "xhigh"]
