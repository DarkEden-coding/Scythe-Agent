from app.providers.reasoning import extract_reasoning_capabilities


def test_openrouter_supported_parameters_reasoning_uses_provider_defaults() -> None:
    caps = extract_reasoning_capabilities(
        provider="openrouter",
        model_label="openai/gpt-5",
        raw_model={"supported_parameters": ["max_tokens", "reasoning"]},
    )

    assert caps.supported is True
    assert caps.levels == ("minimal", "low", "medium", "high")
    assert caps.default_level == "medium"


def test_groq_reasoning_effort_signal_uses_groq_defaults() -> None:
    caps = extract_reasoning_capabilities(
        provider="groq",
        model_label="llama-3.3-70b-versatile",
        raw_model={"supported_parameters": ["reasoning_effort", "tools"]},
    )

    assert caps.supported is True
    assert caps.levels == ("low", "medium", "high")
    assert caps.default_level == "medium"


def test_openai_sub_gpt5_heuristic_defaults() -> None:
    caps = extract_reasoning_capabilities(
        provider="openai-sub",
        model_label="gpt-5.3-codex",
        raw_model={},
    )

    assert caps.supported is True
    assert caps.levels == ("minimal", "low", "medium", "high")
    assert caps.default_level == "medium"


def test_explicit_reasoning_levels_and_default_are_respected() -> None:
    caps = extract_reasoning_capabilities(
        provider="openrouter",
        model_label="custom/reasoner",
        raw_model={"reasoning": {"efforts": ["low", "high"], "default": "high"}},
    )

    assert caps.supported is True
    assert caps.levels == ("low", "high")
    assert caps.default_level == "high"


def test_non_reasoning_model_stays_unsupported() -> None:
    caps = extract_reasoning_capabilities(
        provider="openrouter",
        model_label="anthropic/claude-3.5-sonnet",
        raw_model={"supported_parameters": ["max_tokens", "temperature", "tools"]},
    )

    assert caps.supported is False
    assert caps.levels == ()
    assert caps.default_level is None
