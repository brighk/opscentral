import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, role: str = "admin"):
    """Helper to register and return auth headers."""
    reg = await client.post("/api/v1/auth/register", json={
        "email": f"{role}@test.com",
        "password": "testpass123",
        "full_name": "Test User",
        "company_name": "Test Corp",
    })
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestPagination:
    async def test_pagination_agents(self, client: AsyncClient):
        headers = await _register_and_login(client)

        # Register some agents
        for i in range(3):
            await client.post("/api/v1/agents/register", json={
                "hostname": f"agent-{i}",
                "os_type": "linux",
            }, headers=headers)

        # Test paginated list
        resp = await client.get("/api/v1/agents?page=1&page_size=2", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert "pages" in data
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["pages"] == 2

        # Page 2
        resp = await client.get("/api/v1/agents?page=2&page_size=2", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    async def test_pagination_assets(self, client: AsyncClient):
        headers = await _register_and_login(client)

        # Assets are created via inventory - just test the endpoint works
        resp = await client.get("/api/v1/assets?page=1&page_size=10", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestAPIKeys:
    async def test_create_api_key(self, client: AsyncClient):
        headers = await _register_and_login(client)

        resp = await client.post("/api/v1/api-keys", json={
            "name": "My API Key",
            "scopes": ["read"],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "raw_key" in data
        assert data["raw_key"].startswith("oc_")
        assert data["name"] == "My API Key"
        assert data["is_active"] is True

    async def test_list_api_keys(self, client: AsyncClient):
        headers = await _register_and_login(client)

        # Create a key first
        await client.post("/api/v1/api-keys", json={
            "name": "Test Key",
        }, headers=headers)

        resp = await client.get("/api/v1/api-keys", headers=headers)
        assert resp.status_code == 200
        keys = resp.json()
        assert len(keys) == 1
        assert keys[0]["name"] == "Test Key"
        assert "raw_key" not in keys[0]  # Raw key only returned on create

    async def test_revoke_api_key(self, client: AsyncClient):
        headers = await _register_and_login(client)

        # Create
        create_resp = await client.post("/api/v1/api-keys", json={
            "name": "To Revoke",
        }, headers=headers)
        key_id = create_resp.json()["id"]

        # Revoke
        resp = await client.delete(f"/api/v1/api-keys/{key_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "revoked"

        # Verify revoked
        list_resp = await client.get("/api/v1/api-keys", headers=headers)
        keys = list_resp.json()
        assert keys[0]["is_active"] is False


class TestSecurityHeaders:
    async def test_security_headers_present(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"


class TestErrorFormat:
    async def test_error_response_format(self, client: AsyncClient):
        # 404 error
        resp = await client.get("/api/v1/assets/00000000-0000-0000-0000-000000000000",
                                headers={"Authorization": "Bearer invalid"})
        # Should get 401 or 403
        assert resp.status_code in (401, 403, 422)
        data = resp.json()
        assert "detail" in data
