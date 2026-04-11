import pytest


async def _setup(client, email="search@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Search User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]


@pytest.mark.asyncio
async def test_search_pages(client):
    token, pid = await _setup(client)
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/ml.md", "type": "entity", "title": "Machine Learning", "content": "Deep learning is great"}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/db.md", "type": "entity", "title": "Databases", "content": "SQL and NoSQL"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/search?q=learning", headers=h)
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Machine Learning"


@pytest.mark.asyncio
async def test_search_empty(client):
    token, pid = await _setup(client, "search2@example.com")
    resp = await client.get(f"/api/v1/projects/{pid}/search?q=nonexistent", headers={"Authorization": f"Bearer {token}"})
    assert resp.json() == []
