import pytest


async def _setup(client, email="lint@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Lint User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]


@pytest.mark.asyncio
async def test_lint_empty_project(client):
    token, pid = await _setup(client)
    resp = await client.get(f"/api/v1/projects/{pid}/lint", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert "issues" in resp.json()


@pytest.mark.asyncio
async def test_lint_finds_empty_page(client):
    token, pid = await _setup(client, "lint2@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/empty.md", "type": "entity", "title": "Empty", "content": ""}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/lint", headers=h)
    issues = resp.json()["issues"]
    assert any(i["type"] == "empty_page" for i in issues)


@pytest.mark.asyncio
async def test_lint_finds_broken_wikilink(client):
    token, pid = await _setup(client, "lint3@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/a.md", "type": "entity", "title": "A", "content": "See [[NonExistent]]"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/lint", headers=h)
    issues = resp.json()["issues"]
    assert any(i["type"] == "broken_wikilink" for i in issues)
