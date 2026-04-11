async def _register(client, email="cfg@example.com"):
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "secret123", "display_name": "Cfg User"
    })
    return resp.json()["access_token"]

async def test_get_config_empty(client):
    token = await _register(client)
    resp = await client.get("/api/v1/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

async def test_put_user_config(client):
    token = await _register(client, "put@example.com")
    resp = await client.put("/api/v1/config", json={
        "llm_config": {"provider": "openrouter", "model": "claude-sonnet-4"}
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    get_resp = await client.get("/api/v1/config", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.json()["llm_config"]["provider"] == "openrouter"

async def test_admin_config_requires_admin(client):
    token = await _register(client, "nonadmin@example.com")
    resp = await client.get("/api/v1/admin/config", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
