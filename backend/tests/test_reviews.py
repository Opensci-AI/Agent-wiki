import pytest


async def _setup(client, email="review@example.com"):
    reg = await client.post("/api/v1/auth/register", json={"email": email, "password": "secret123", "display_name": "Review User"})
    token = reg.json()["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "Wiki"}, headers={"Authorization": f"Bearer {token}"})
    return token, proj.json()["id"]


@pytest.mark.asyncio
async def test_list_reviews_empty(client):
    token, pid = await _setup(client)
    resp = await client.get(f"/api/v1/projects/{pid}/reviews", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_patch_review_not_found(client):
    token, pid = await _setup(client, "review2@example.com")
    resp = await client.patch(
        f"/api/v1/projects/{pid}/reviews/00000000-0000-0000-0000-000000000001",
        json={"resolved": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
