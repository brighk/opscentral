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


async def _setup_agent(client: AsyncClient, headers: dict):
    """Register an agent and return (agent_id, api_key)."""
    resp = await client.post("/api/v1/agents/register", json={
        "hostname": "test-agent",
        "os_type": "linux",
    }, headers=headers)
    data = resp.json()
    return data["agent_id"], data["api_key"]


class TestRemoteActions:
    async def test_list_action_types(self, client: AsyncClient):
        resp = await client.get("/api/v1/remote-actions/types")
        assert resp.status_code == 200
        types = resp.json()
        assert len(types) > 0
        type_keys = [t["key"] for t in types]
        assert "restart_service" in type_keys
        assert "custom_script" in type_keys

    async def test_create_action(self, client: AsyncClient):
        headers = await _register_and_login(client)
        agent_id, _ = await _setup_agent(client, headers)

        resp = await client.post("/api/v1/remote-actions", json={
            "agent_id": agent_id,
            "action_type": "health_check",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert data["action_type"] == "health_check"
        assert data["agent_id"] == agent_id

    async def test_custom_script_requires_admin(self, client: AsyncClient):
        admin_headers = await _register_and_login(client)
        operator_headers = await _create_operator(client, admin_headers)
        agent_id, _ = await _setup_agent(client, admin_headers)

        resp = await client.post("/api/v1/remote-actions", json={
            "agent_id": agent_id,
            "action_type": "custom_script",
            "parameters": {"script": "echo hello"},
        }, headers=operator_headers)
        assert resp.status_code == 403

    async def test_agent_poll_actions(self, client: AsyncClient):
        headers = await _register_and_login(client)
        agent_id, api_key = await _setup_agent(client, headers)
        agent_headers = {"X-Agent-Key": api_key}

        # Create an action
        await client.post("/api/v1/remote-actions", json={
            "agent_id": agent_id,
            "action_type": "collect_diagnostics",
        }, headers=headers)

        # Agent polls
        resp = await client.get("/api/v1/gateway/actions/poll", headers=agent_headers)
        assert resp.status_code == 200
        actions = resp.json()
        assert len(actions) == 1
        assert actions[0]["action_type"] == "collect_diagnostics"

        # Poll again - should be empty (already dispatched)
        resp2 = await client.get("/api/v1/gateway/actions/poll", headers=agent_headers)
        assert resp2.status_code == 200
        assert len(resp2.json()) == 0

    async def test_agent_report_result(self, client: AsyncClient):
        headers = await _register_and_login(client)
        agent_id, api_key = await _setup_agent(client, headers)
        agent_headers = {"X-Agent-Key": api_key}

        # Create and poll action
        create_resp = await client.post("/api/v1/remote-actions", json={
            "agent_id": agent_id,
            "action_type": "health_check",
        }, headers=headers)
        action_id = create_resp.json()["id"]

        # Poll to dispatch
        await client.get("/api/v1/gateway/actions/poll", headers=agent_headers)

        # Report result
        resp = await client.post(f"/api/v1/gateway/actions/{action_id}/result", json={
            "status": "completed",
            "result": {"cpu_percent": 25.0, "network": "ok"},
        }, headers=agent_headers)
        assert resp.status_code == 200

        # Verify via user endpoint
        detail_resp = await client.get(f"/api/v1/remote-actions/{action_id}", headers=headers)
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert data["status"] == "completed"
        assert data["result"]["cpu_percent"] == 25.0

    async def test_cancel_action(self, client: AsyncClient):
        headers = await _register_and_login(client)
        agent_id, _ = await _setup_agent(client, headers)

        create_resp = await client.post("/api/v1/remote-actions", json={
            "agent_id": agent_id,
            "action_type": "restart_service",
            "parameters": {"service_name": "nginx"},
        }, headers=headers)
        action_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/remote-actions/{action_id}/cancel", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
