async def _setup(client, email="src@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Src User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]


async def test_upload_txt(client):
    token, pid = await _setup(client)
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("notes.txt", b"hello world", "text/plain")}, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_type"] == "txt"
    assert data["status"] == "ready"
    assert data["extracted_text"] == "hello world"


async def test_upload_pdf(client):
    token, pid = await _setup(client, "pdf@example.com")
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("paper.pdf", b"%PDF-fake", "application/pdf")}, headers=h)
    assert resp.status_code == 201
    # PDFs are auto-extracted on upload; fake PDF will fail extraction gracefully
    assert resp.json()["status"] == "ready"
    # Extraction may fail or return error message for invalid PDF
    assert resp.json()["extracted_text"] is not None


async def test_upload_unsupported(client):
    token, pid = await _setup(client, "bad@example.com")
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("virus.exe", b"bad", "application/octet-stream")}, headers=h)
    assert resp.status_code == 400


async def test_clip(client):
    token, pid = await _setup(client, "clip@example.com")
    h = {"Authorization": f"Bearer {token}"}
    resp = await client.post(f"/api/v1/projects/{pid}/sources/clip", json={
        "title": "Interesting Article", "url": "https://example.com/article", "content": "Article body here"
    }, headers=h)
    assert resp.status_code == 201
    data = resp.json()
    assert data["content_type"] == "clip"
    assert data["status"] == "ready"
    assert "web-clip" in data["extracted_text"]


async def test_list_sources(client):
    token, pid = await _setup(client, "listsrc@example.com")
    h = {"Authorization": f"Bearer {token}"}
    await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("a.txt", b"aa", "text/plain")}, headers=h)
    await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("b.md", b"bb", "text/plain")}, headers=h)
    resp = await client.get(f"/api/v1/projects/{pid}/sources", headers=h)
    assert len(resp.json()) == 2


async def test_get_source(client):
    token, pid = await _setup(client, "getsrc@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("x.txt", b"xx", "text/plain")}, headers=h)
    sid = created.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/sources/{sid}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["extracted_text"] == "xx"


async def test_delete_source(client):
    token, pid = await _setup(client, "delsrc@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("del.txt", b"del", "text/plain")}, headers=h)
    sid = created.json()["id"]
    resp = await client.delete(f"/api/v1/projects/{pid}/sources/{sid}", headers=h)
    assert resp.status_code == 204
    get_resp = await client.get(f"/api/v1/projects/{pid}/sources/{sid}", headers=h)
    assert get_resp.status_code == 404


async def test_serve_file_with_header(client):
    token, pid = await _setup(client, "serve@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("hello.txt", b"hello world", "text/plain")}, headers=h)
    sid = created.json()["id"]
    resp = await client.get(f"/api/v1/projects/{pid}/sources/{sid}/file", headers=h)
    assert resp.status_code == 200
    assert resp.content == b"hello world"
    assert "text/plain" in resp.headers["content-type"]
    assert 'filename="hello.txt"' in resp.headers.get("content-disposition", "")


async def test_serve_file_with_query_token(client):
    token, pid = await _setup(client, "serveq@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("pic.png", b"\x89PNG fake", "image/png")}, headers=h)
    sid = created.json()["id"]
    # Authenticate via query param instead of header (like <img> tags do)
    resp = await client.get(f"/api/v1/projects/{pid}/sources/{sid}/file?token={token}")
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG fake"
    assert "image/png" in resp.headers["content-type"]


async def test_serve_file_unauthenticated(client):
    token, pid = await _setup(client, "serveno@example.com")
    h = {"Authorization": f"Bearer {token}"}
    created = await client.post(f"/api/v1/projects/{pid}/sources/upload",
        files={"file": ("sec.txt", b"secret", "text/plain")}, headers=h)
    sid = created.json()["id"]
    # No auth at all
    resp = await client.get(f"/api/v1/projects/{pid}/sources/{sid}/file")
    assert resp.status_code == 401
