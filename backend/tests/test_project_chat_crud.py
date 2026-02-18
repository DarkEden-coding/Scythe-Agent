def test_project_and_chat_crud_roundtrip(client) -> None:
    created_project = client.post(
        "/api/projects",
        json={"name": "tmp-project", "path": "."},
    )
    assert created_project.status_code == 200
    payload = created_project.json()
    assert payload["ok"] is True
    project_id = payload["data"]["project"]["id"]

    created_chat = client.post(
        f"/api/projects/{project_id}/chats",
        json={"title": "hello"},
    )
    assert created_chat.status_code == 200
    chat_id = created_chat.json()["data"]["chat"]["id"]

    rename_chat = client.patch(f"/api/chats/{chat_id}", json={"title": "hello-updated", "isPinned": True})
    assert rename_chat.status_code == 200
    rename_data = rename_chat.json()["data"]["chat"]
    assert rename_data["title"] == "hello-updated"
    assert rename_data["isPinned"] is True

    delete_chat = client.delete(f"/api/chats/{chat_id}")
    assert delete_chat.status_code == 200
    assert delete_chat.json()["data"]["deletedChatId"] == chat_id

    delete_project = client.delete(f"/api/projects/{project_id}")
    assert delete_project.status_code == 200
    assert delete_project.json()["data"]["deletedProjectId"] == project_id


def test_fs_children_contract_and_guard(client) -> None:
    success = client.get("/api/fs/children")
    assert success.status_code == 200
    body = success.json()
    assert body["ok"] is True
    data = body["data"]
    assert "path" in data
    assert "children" in data
    assert "allowedRoots" in data
    assert isinstance(data["children"], list)
    if data["children"]:
        child = data["children"][0]
        assert {"name", "path", "kind", "hasChildren"} <= set(child.keys())

    any_path = client.get("/api/fs/children", params={"path": "/etc"})
    any_body = any_path.json()
    assert any_body["ok"] is True
    assert "path" in any_body["data"] and "children" in any_body["data"]
