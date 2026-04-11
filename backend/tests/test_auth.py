import pytest

async def test_register(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "new@example.com",
        "password": "secret123",
        "display_name": "New User"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

async def test_register_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "secret123", "display_name": "Dup"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409
    assert "already registered" in resp.json()["detail"]

async def test_login_success(client):
    await client.post("/api/v1/auth/register", json={
        "email": "login@example.com", "password": "secret123", "display_name": "Login User"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "login@example.com", "password": "secret123"
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()

async def test_login_wrong_password(client):
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@example.com", "password": "secret123", "display_name": "Wrong"
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "wrong@example.com", "password": "badpassword"
    })
    assert resp.status_code == 401

async def test_get_me(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "me@example.com", "password": "secret123", "display_name": "Me"
    })
    token = reg.json()["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"

async def test_get_me_no_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 422 or resp.status_code == 401

async def test_refresh_token(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "refresh@example.com", "password": "secret123", "display_name": "Refresh"
    })
    refresh_cookie = reg.cookies.get("refresh_token")
    assert refresh_cookie is not None
    resp = await client.post("/api/v1/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert resp.status_code == 200
    assert "access_token" in resp.json()

async def test_refresh_no_cookie(client):
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401

async def test_oauth_redirect_google(client):
    resp = await client.get("/api/v1/auth/oauth/google", follow_redirects=False)
    assert resp.status_code == 307
    assert "accounts.google.com" in resp.headers["location"]

async def test_oauth_redirect_github(client):
    resp = await client.get("/api/v1/auth/oauth/github", follow_redirects=False)
    assert resp.status_code == 307
    assert "github.com" in resp.headers["location"]

async def test_oauth_invalid_provider(client):
    resp = await client.get("/api/v1/auth/oauth/twitter", follow_redirects=False)
    assert resp.status_code == 400
