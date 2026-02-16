from uuid import uuid4


def generate_id(prefix: str) -> str:
    """Generate a prefixed short UUID, e.g. 'msg-a1b2c3d4e5f6'."""
    return f"{prefix}-{uuid4().hex[:12]}"
