def map_role_for_ui(role: str) -> str:
    return "agent" if role == "assistant" else role


def map_file_action_for_ui(action: str) -> str:
    mapping = {
        "created": "create",
        "modified": "edit",
        "deleted": "delete",
    }
    return mapping.get(action, action)
