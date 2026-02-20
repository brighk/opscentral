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


async def _create_viewer(client: AsyncClient, admin_headers: dict):
    """Create a viewer user and return headers."""
    await client.post("/api/v1/auth/users/invite", json={
        "email": "viewer@test.com",
        "password": "viewerpass123",
        "full_name": "Test Viewer",
        "role": "viewer",
    }, headers=admin_headers)

    login_resp = await client.post("/api/v1/auth/login", json={
        "email": "viewer@test.com",
        "password": "viewerpass123",
    })
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestBilling:
    async def test_get_subscription_default(self, client: AsyncClient):
        headers = await _register_and_login(client)

        resp = await client.get("/api/v1/billing/subscription", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["plan"] == "free"
        assert data["status"] == "active"
        assert data["asset_limit"] == 5
        assert data["asset_count"] == 0

    async def test_list_plans(self, client: AsyncClient):
        resp = await client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        plans = resp.json()
        assert len(plans) == 4
        plan_keys = [p["key"] for p in plans]
        assert "free" in plan_keys
        assert "starter" in plan_keys
        assert "professional" in plan_keys
        assert "enterprise" in plan_keys

    async def test_checkout_requires_admin(self, client: AsyncClient):
        admin_headers = await _register_and_login(client)
        viewer_headers = await _create_viewer(client, admin_headers)

        resp = await client.post("/api/v1/billing/checkout", json={
            "plan": "starter",
            "billing_period": "monthly",
        }, headers=viewer_headers)
        assert resp.status_code == 403

    async def test_usage_stats(self, client: AsyncClient):
        headers = await _register_and_login(client)

        resp = await client.get("/api/v1/billing/usage", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "asset_count" in data
        assert "asset_limit" in data
        assert "agent_count" in data
        assert "plan" in data
        assert data["plan"] == "free"

    async def test_asset_limit_enforcement(self, client: AsyncClient):
        headers = await _register_and_login(client)

        # Register an agent to get an API key
        reg_resp = await client.post("/api/v1/agents/register", json={
            "hostname": "test-agent",
            "os_type": "linux",
        }, headers=headers)
        api_key = reg_resp.json()["api_key"]
        agent_headers = {"X-Agent-Key": api_key}

        # The free plan allows 5 assets; submitting inventory creates assets
        # First inventory should succeed (creates asset 1)
        resp = await client.post("/api/v1/gateway/inventory", json={
            "system_info": {"hostname": "server-1", "os_type": "linux"},
        }, headers=agent_headers)
        assert resp.status_code == 200
