async def _register(client, email="proj@example.com"):
    resp = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "secret123", "display_name": "Proj User"
    })
    return resp.json()["access_token"]

async def test_create_project(client):
    token = await _register(client)
    resp = await client.post("/api/v1/projects", json={"name": "My Wiki"},
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Wiki"
    assert "id" in data

async def test_list_projects(client):
    token = await _register(client, "list@example.com")
    await client.post("/api/v1/projects", json={"name": "Wiki 1"},
        headers={"Authorization": f"Bearer {token}"})
    await client.post("/api/v1/projects", json={"name": "Wiki 2"},
        headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2

async def test_get_project(client):
    token = await _register(client, "get@example.com")
    create = await client.post("/api/v1/projects", json={"name": "Detail Wiki"},
        headers={"Authorization": f"Bearer {token}"})
    pid = create.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Detail Wiki"

async def test_get_project_not_owner(client):
    token1 = await _register(client, "owner1@example.com")
    token2 = await _register(client, "owner2@example.com")
    create = await client.post("/api/v1/projects", json={"name": "Private"},
        headers={"Authorization": f"Bearer {token1}"})
    pid = create.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 404

async def test_update_project(client):
    token = await _register(client, "update@example.com")
    create = await client.post("/api/v1/projects", json={"name": "Old Name"},
        headers={"Authorization": f"Bearer {token}"})
    pid = create.json()["id"]
    resp = await client.patch(f"/api/v1/projects/{pid}", json={"name": "New Name"},
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"

async def test_delete_project(client):
    token = await _register(client, "delete@example.com")
    create = await client.post("/api/v1/projects", json={"name": "To Delete"},
        headers={"Authorization": f"Bearer {token}"})
    pid = create.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
    list_resp = await client.get("/api/v1/projects",
        headers={"Authorization": f"Bearer {token}"})
    assert len(list_resp.json()) == 0
    # Verify GET by ID also returns 404 for deleted project
    get_resp = await client.get(f"/api/v1/projects/{pid}",
        headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 404
