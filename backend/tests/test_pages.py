async def _setup(client, email="pages@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Pages User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]

async def test_create_page(client):
    token, pid = await _setup(client)
    resp = await client.post(f"/api/v1/projects/{pid}/pages", json={
        "path": "entities/ml.md", "type": "entity", "title": "Machine Learning", "content": "# ML"
    }, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Machine Learning"

async def test_list_pages(client):
    token, pid = await _setup(client, "list-pages@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/a.md", "type": "entity", "title": "A"}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "concepts/b.md", "type": "concept", "title": "B"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/pages", headers=h)
    assert len(resp.json()) == 2
    resp2 = await client.get(f"/api/v1/projects/{pid}/pages?type=entity", headers=h)
    assert len(resp2.json()) == 1

async def test_get_page(client):
    token, pid = await _setup(client, "get-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/x.md", "type": "entity", "title": "X"}, headers=h)
    page_id = created.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/pages/{page_id}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["title"] == "X"

async def test_get_by_path(client):
    token, pid = await _setup(client, "bypath@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/find-me.md", "type": "entity", "title": "FindMe"}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/pages/by-path?path=entities/find-me.md", headers=h)
    assert resp.status_code == 200
    assert resp.json()["title"] == "FindMe"

async def test_update_page(client):
    token, pid = await _setup(client, "update-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/u.md", "type": "entity", "title": "Old"}, headers=h)
    page_id = created.json()["id"]
    resp = await client.put(f"/api/v1/projects/{pid}/pages/{page_id}", json={"title": "New", "content": "updated"}, headers=h)
    assert resp.json()["title"] == "New"
    assert resp.json()["content"] == "updated"

async def test_delete_page(client):
    token, pid = await _setup(client, "del-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/d.md", "type": "entity", "title": "D"}, headers=h)
    page_id = created.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}/pages/{page_id}", headers=h)
    assert resp.status_code == 204
    get_resp = await client.get(f"/api/v1/projects/{pid}/pages/{page_id}", headers=h)
    assert get_resp.status_code == 404

async def test_duplicate_path(client):
    token, pid = await _setup(client, "dup-page@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/same.md", "type": "entity", "title": "First"}, headers=h)
    resp = await client.post(f"/api/v1/projects/{pid}/pages", json={"path": "entities/same.md", "type": "entity", "title": "Second"}, headers=h)
    assert resp.status_code == 409

async def test_find_related(client):
    token, pid = await _setup(client, "related@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/pages", json={
        "path": "entities/ml.md", "type": "entity", "title": "ML",
        "frontmatter": {"sources": ["paper.pdf"]}
    }, headers=h)
    await client.post(f"/api/v1/projects/{pid}/pages", json={
        "path": "entities/dl.md", "type": "entity", "title": "DL",
        "frontmatter": {"sources": ["other.pdf"]}
    }, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/pages/related?source=paper.pdf", headers=h)
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "ML"
