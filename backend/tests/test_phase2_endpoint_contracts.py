def _assert_envelope(payload: dict) -> None:
    assert isinstance(payload.get("ok"), bool)
    assert "timestamp" in payload
    if payload["ok"]:
        assert payload.get("data") is not None


def test_get_projects_contract(client) -> None:
    response = client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    data = body["data"]
    assert "projects" in data
    assert isinstance(data["projects"], list)
    assert data["projects"]
    p = data["projects"][0]
    for field in ["id", "name", "path", "lastAccessed", "chats"]:
        assert field in p
    assert isinstance(p["chats"], list)


def test_get_settings_contract(client) -> None:
    response = client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    data = body["data"]
    for field in ["model", "availableModels", "contextLimit", "autoApproveRules"]:
        assert field in data
    assert isinstance(data["availableModels"], list)


def test_get_chat_history_contract_and_mapping(client) -> None:
    response = client.get("/api/chat/chat-1/history")
    assert response.status_code == 200
    body = response.json()
    _assert_envelope(body)
    data = body["data"]
    for field in [
        "chatId",
        "messages",
        "toolCalls",
        "fileEdits",
        "checkpoints",
        "reasoningBlocks",
        "contextItems",
        "maxTokens",
        "model",
    ]:
        assert field in data
    assert data["chatId"] == "chat-1"
    assert isinstance(data["messages"], list)
    assert isinstance(data["fileEdits"], list)
    if data["messages"]:
        roles = {m["role"] for m in data["messages"]}
        assert "agent" in roles or "user" in roles
    if data["fileEdits"]:
        action = data["fileEdits"][0]["action"]
        assert action in {"create", "edit", "delete"}

