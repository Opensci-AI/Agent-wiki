import pytest


async def _setup(client, email="graph@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Graph User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]


@pytest.mark.asyncio
async def test_empty_graph(client):
    token, pid = await _setup(client)
    resp = await client.get(f"/api/v1/projects/{pid}/graph", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["nodes"] == []
    assert resp.json()["edges"] == []


@pytest.mark.asyncio
async def test_graph_with_pages(client):
    token, pid = await _setup(client, "graph2@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/a.md", "type": "entity", "title": "A", "content": "Links to [[B]]"}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/b.md", "type": "entity", "title": "B", "content": "Standalone"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/graph", headers=h)
    data = resp.json()
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) >= 1


@pytest.mark.asyncio
async def test_graph_insights(client):
    token, pid = await _setup(client, "graph3@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/a.md", "type": "entity", "title": "A", "content": "Links to [[B]]"}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/b.md", "type": "entity", "title": "B", "content": "Standalone"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/graph/insights", headers=h)
    data = resp.json()
    assert "orphans" in data
    assert "hubs" in data
    # A has no incoming links, so it should be an orphan
    orphan_titles = [o["title"] for o in data["orphans"]]
    assert "A" in orphan_titles
