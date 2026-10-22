import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.usefixtures("inline_runbooks")


async def _register_and_login(client: AsyncClient, email: str = "admin@test.com"):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "full_name": "Test Admin",
            "company_name": "Test Corp",
        },
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _create_operator(client: AsyncClient, admin_headers: dict):
    await client.post(
        "/api/v1/auth/users/invite",
        json={
            "email": "operator@test.com",
            "password": "operatorpass123",
            "full_name": "Test Operator",
            "role": "operator",
        },
        headers=admin_headers,
    )

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "operator@test.com",
            "password": "operatorpass123",
        },
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _setup_agent(client: AsyncClient, headers: dict) -> str:
    resp = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "web-1", "os_type": "linux"},
        headers=headers,
    )
    return resp.json()["agent_id"]


class TestRunbooks:
    async def test_create_runbook(self, client: AsyncClient):
        headers = await _register_and_login(client)
        agent_id = await _setup_agent(client, headers)
        resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "Restart Service",
                "description": "Restart nginx on target server",
                "steps": [
                    {
                        "name": "Restart Service",
                        "action_type": "remote_action",
                        "parameters": {
                            "agent_id": agent_id,
                            "action": "restart_service",
                            "parameters": {"service_name": "nginx"},
                        },
                        "on_failure": "stop",
                    },
                    {
                        "name": "Wait",
                        "action_type": "delay",
                        "parameters": {"seconds": 5},
                        "on_failure": "stop",
                    },
                ],
                "trigger_type": "manual",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Restart Service"
        assert len(data["steps"]) == 2
        # Parameters are stored normalized, with defaults filled in
        assert data["steps"][0]["parameters"]["timeout_seconds"] == 300

    async def test_list_runbooks(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post(
            "/api/v1/runbooks",
            json={
                "name": "Test RB",
                "steps": [
                    {
                        "name": "Step 1",
                        "action_type": "delay",
                        "parameters": {},
                        "on_failure": "stop",
                    }
                ],
            },
            headers=headers,
        )
        resp = await client.get("/api/v1/runbooks", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_update_runbook(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "Original",
                "steps": [
                    {"name": "S1", "action_type": "delay", "parameters": {}, "on_failure": "stop"}
                ],
            },
            headers=headers,
        )
        rb_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/runbooks/{rb_id}",
            json={
                "name": "Updated",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"

    async def test_delete_runbook(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "To Delete",
                "steps": [
                    {"name": "S1", "action_type": "delay", "parameters": {}, "on_failure": "stop"}
                ],
            },
            headers=headers,
        )
        rb_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/runbooks/{rb_id}", headers=headers)
        assert resp.status_code == 200

    async def test_execute_runbook_no_approval(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "Auto Run",
                "steps": [
                    {
                        "name": "Step 1",
                        "action_type": "delay",
                        "parameters": {"seconds": 0},
                        "on_failure": "continue",
                    },
                ],
                "requires_approval": False,
            },
            headers=headers,
        )
        rb_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/runbooks/{rb_id}/execute", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"

    async def test_execute_runbook_with_approval(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "Needs Approval",
                "steps": [
                    {
                        "name": "Step 1",
                        "action_type": "delay",
                        "parameters": {},
                        "on_failure": "stop",
                    },
                ],
                "requires_approval": True,
            },
            headers=headers,
        )
        rb_id = create_resp.json()["id"]

        exec_resp = await client.post(f"/api/v1/runbooks/{rb_id}/execute", headers=headers)
        assert exec_resp.status_code == 200
        assert exec_resp.json()["status"] == "pending_approval"

    async def test_approve_execution(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "Approve Me",
                "steps": [
                    {"name": "S1", "action_type": "delay", "parameters": {}, "on_failure": "stop"}
                ],
                "requires_approval": True,
            },
            headers=headers,
        )
        rb_id = create_resp.json()["id"]

        exec_resp = await client.post(f"/api/v1/runbooks/{rb_id}/execute", headers=headers)
        exec_id = exec_resp.json()["id"]

        approve_resp = await client.post(
            f"/api/v1/runbooks/executions/{exec_id}/approve", headers=headers
        )
        assert approve_resp.status_code == 200
        assert approve_resp.json()["status"] == "completed"

    async def test_cancel_execution(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "Cancel Me",
                "steps": [
                    {"name": "S1", "action_type": "delay", "parameters": {}, "on_failure": "stop"}
                ],
                "requires_approval": True,
            },
            headers=headers,
        )
        rb_id = create_resp.json()["id"]

        exec_resp = await client.post(f"/api/v1/runbooks/{rb_id}/execute", headers=headers)
        exec_id = exec_resp.json()["id"]

        cancel_resp = await client.post(
            f"/api/v1/runbooks/executions/{exec_id}/cancel", headers=headers
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["status"] == "cancelled"

    async def test_list_executions(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/runbooks",
            json={
                "name": "List Execs",
                "steps": [
                    {"name": "S1", "action_type": "delay", "parameters": {}, "on_failure": "stop"}
                ],
            },
            headers=headers,
        )
        rb_id = create_resp.json()["id"]

        await client.post(f"/api/v1/runbooks/{rb_id}/execute", headers=headers)

        resp = await client.get(f"/api/v1/runbooks/{rb_id}/executions", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
