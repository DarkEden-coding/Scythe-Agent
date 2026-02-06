"""Static defaults for Phase 0-2 MVP."""

FALLBACK_MODELS = [
    "anthropic/claude-3.5-sonnet",
    "openai/gpt-4o",
    "openai/gpt-4.1",
]

DEFAULT_ACTIVE_MODEL = FALLBACK_MODELS[0]
DEFAULT_CONTEXT_LIMIT = 128000

