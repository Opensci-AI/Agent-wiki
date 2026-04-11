async def _setup(client, email="chat@example.com"):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secret123",
            "display_name": "Chat User",
        },
    )
    token = reg.json()["access_token"]
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "Wiki"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return token, proj.json()["id"]


async def test_create_conversation(client):
    token, pid = await _setup(client)
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(
        f"/api/v1/projects/{pid}/conversations",
        json={"title": "Test Chat"},
        headers=h,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Test Chat"


async def test_list_conversations(client):
    token, pid = await _setup(client, "list-chat@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(
        f"/api/v1/projects/{pid}/conversations",
        json={"title": "Chat 1"},
        headers=h,
    )
    await client.post(
        f"/api/v1/projects/{pid}/conversations",
        json={"title": "Chat 2"},
        headers=h,
    )
    resp = await client.get(
        f"/api/v1/projects/{pid}/conversations", headers=h
    )
    assert len(resp.json()) == 2


async def test_send_and_get_messages(client):
    token, pid = await _setup(client, "msg@example.com")
    h = {"Authorization": f"Bearer {token}"}
    conv = await client.post(
        f"/api/v1/projects/{pid}/conversations",
        json={"title": "Msg"},
        headers=h,
    )
    conv_id = conv.json()["id"]
    await client.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"content": "Hello"},
        headers=h,
    )
    resp = await client.get(
        f"/api/v1/conversations/{conv_id}/messages", headers=h
    )
    assert len(resp.json()) == 1
    assert resp.json()[0]["role"] == "user"


async def test_delete_conversation(client):
    token, pid = await _setup(client, "del-chat@example.com")
    h = {"Authorization": f"Bearer {token}"}
    conv = await client.post(
        f"/api/v1/projects/{pid}/conversations",
        json={"title": "Del"},
        headers=h,
    )
    conv_id = conv.json()["id"]
    resp = await client.delete(
        f"/api/v1/conversations/{conv_id}", headers=h
    )
    assert resp.status_code == 204
