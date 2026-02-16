import json


def safe_parse_json(raw: str) -> dict:
    """Parse JSON string to dict, returning empty dict on failure."""
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
