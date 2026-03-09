from app.providers.vision import model_has_vision


class _StubSettingsRepo:
    def __init__(self, models: list[object] | None = None) -> None:
        self._models = models or []

    def list_models(self) -> list[object]:
        return self._models


def test_openai_sub_defaults_to_vision_when_metadata_is_missing() -> None:
    repo = _StubSettingsRepo()

    assert model_has_vision("openai-sub", "gpt-5.3-codex", repo, raw_model={}) is True


def test_openai_sub_respects_explicit_non_vision_metadata() -> None:
    repo = _StubSettingsRepo()
    raw = {"supportsImages": False, "capabilities": ["text"]}

    assert model_has_vision("openai-sub", "gpt-5.3-codex-spark", repo, raw_model=raw) is False


def test_openai_sub_fallback_defaults_to_vision_when_model_not_cached() -> None:
    repo = _StubSettingsRepo()

    assert model_has_vision("openai-sub", "unknown-codex-model", repo, raw_model=None) is True


def test_openai_sub_fallback_uses_known_text_only_model_metadata() -> None:
    repo = _StubSettingsRepo()

    assert model_has_vision("openai-sub", "gpt-5.3-codex-spark", repo, raw_model=None) is False


def test_openrouter_unchanged_non_vision_modalities_still_false() -> None:
    repo = _StubSettingsRepo()
    raw = {"modalities": ["text"]}

    assert model_has_vision("openrouter", "some-model", repo, raw_model=raw) is False
