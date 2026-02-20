import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str = "admin@test.com"):
    reg = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "testpass123",
        "full_name": "Test Admin",
        "company_name": "Test Corp",
    })
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_operator(client: AsyncClient, admin_headers: dict):
    await client.post("/api/v1/auth/users/invite", json={
        "email": "operator@test.com",
        "password": "operatorpass123",
        "full_name": "Test Operator",
        "role": "operator",
    }, headers=admin_headers)

    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "operator@test.com",
        "password": "operatorpass123",
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestWebhooks:
    async def test_list_event_types(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.get("/api/v1/webhooks/event-types", headers=headers)
        assert resp.status_code == 200
        types = resp.json()
        assert len(types) > 0
        keys = [t["key"] for t in types]
        assert "alert.fired" in keys

    async def test_create_webhook(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.post("/api/v1/webhooks", json={
            "name": "Test Hook",
            "url": "https://example.com/hook",
            "event_types": ["alert.fired", "alert.resolved"],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Hook"
        assert len(data["event_types"]) == 2

    async def test_list_webhooks(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/webhooks", json={
            "name": "Hook 1",
            "url": "https://example.com/h1",
            "event_types": ["alert.fired"],
        }, headers=headers)
        resp = await client.get("/api/v1/webhooks", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_update_webhook(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post("/api/v1/webhooks", json={
            "name": "Original",
            "url": "https://example.com/orig",
            "event_types": ["alert.fired"],
        }, headers=headers)
        wh_id = create_resp.json()["id"]

        resp = await client.put(f"/api/v1/webhooks/{wh_id}", json={
            "name": "Updated",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    async def test_delete_webhook(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post("/api/v1/webhooks", json={
            "name": "To Delete",
            "url": "https://example.com/del",
            "event_types": ["alert.fired"],
        }, headers=headers)
        wh_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/webhooks/{wh_id}", headers=headers)
        assert resp.status_code == 200

    async def test_create_external_integration(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.post("/api/v1/integrations", json={
            "provider": "pagerduty",
            "name": "PD Integration",
            "config": {"api_key": "test123"},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["provider"] == "pagerduty"

    async def test_list_integrations(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/integrations", json={
            "provider": "jira",
            "name": "Jira",
            "config": {"url": "https://jira.example.com"},
        }, headers=headers)
        resp = await client.get("/api/v1/integrations", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_invalid_provider(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.post("/api/v1/integrations", json={
            "provider": "invalid",
            "name": "Bad",
            "config": {},
        }, headers=headers)
        assert resp.status_code == 400

    async def test_test_integration(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post("/api/v1/integrations", json={
            "provider": "opsgenie",
            "name": "OG Test",
            "config": {"api_key": "test"},
        }, headers=headers)
        int_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/integrations/{int_id}/test", headers=headers)
        assert resp.status_code == 200
        assert "successful" in resp.json()["detail"]
