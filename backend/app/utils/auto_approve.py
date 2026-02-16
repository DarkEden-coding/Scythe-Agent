import json
import os.path


def matches_auto_approve_rules(
    *,
    tool_name: str,
    input_payload: dict,
    rules: list,
) -> bool:
    """Check whether a tool call matches any enabled auto-approve rule."""
    path_value = str(input_payload.get("path", ""))
    _, extension = os.path.splitext(path_value)
    directory = os.path.dirname(path_value)
    payload_text = json.dumps(input_payload)
    for rule in rules:
        if not bool(rule.enabled):
            continue
        if rule.field == "tool" and tool_name == rule.value:
            return True
        if rule.field == "path" and path_value == rule.value:
            return True
        if rule.field == "extension" and extension == rule.value:
            return True
        if rule.field == "directory" and directory.startswith(rule.value):
            return True
        if rule.field == "pattern" and rule.value in payload_text:
            return True
    return False
