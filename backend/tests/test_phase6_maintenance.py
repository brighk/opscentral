"""Phase 6: Maintenance Windows tests."""

from datetime import datetime, timedelta, timezone

from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str = "admin@test.com"):
    reg = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "testpass123",
        "full_name": "Test Admin",
        "company_name": "Test Corp",
    })
    data = reg.json()
    return {"Authorization": f"Bearer {data['access_token']}"}


def _future(minutes: int = 60) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _past(minutes: int = 60) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


class TestMaintenanceCRUD:
    async def test_create_window(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.post("/api/v1/maintenance", json={
            "name": "DB Upgrade",
            "start_time": _past(30),
            "end_time": _future(30),
            "scope": "all",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "DB Upgrade"
        assert data["scope"] == "all"
        assert data["is_active"] is True

    async def test_list_windows(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/maintenance", json={
            "name": "Window 1",
            "start_time": _past(10),
            "end_time": _future(10),
            "scope": "all",
        }, headers=headers)
        resp = await client.get("/api/v1/maintenance", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_update_window(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create = await client.post("/api/v1/maintenance", json={
            "name": "Original",
            "start_time": _past(10),
            "end_time": _future(10),
            "scope": "all",
        }, headers=headers)
        wid = create.json()["id"]
        resp = await client.put(f"/api/v1/maintenance/{wid}", json={
            "name": "Updated Name",
            "is_active": False,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["is_active"] is False

    async def test_delete_window(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create = await client.post("/api/v1/maintenance", json={
            "name": "To Delete",
            "start_time": _past(10),
            "end_time": _future(10),
            "scope": "all",
        }, headers=headers)
        wid = create.json()["id"]
        del_resp = await client.delete(f"/api/v1/maintenance/{wid}", headers=headers)
        assert del_resp.status_code == 200
        list_resp = await client.get("/api/v1/maintenance", headers=headers)
        ids = [w["id"] for w in list_resp.json()]
        assert wid not in ids

    async def test_delete_nonexistent_returns_404(self, client: AsyncClient):
        headers = await _register_and_login(client)
        import uuid
        resp = await client.delete(f"/api/v1/maintenance/{uuid.uuid4()}", headers=headers)
        assert resp.status_code == 404

    async def test_create_with_scope_ids(self, client: AsyncClient):
        headers = await _register_and_login(client)
        import uuid
        agent_id = str(uuid.uuid4())
        resp = await client.post("/api/v1/maintenance", json={
            "name": "Agent Window",
            "start_time": _past(5),
            "end_time": _future(5),
            "scope": "agents",
            "scope_ids": [agent_id],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "agents"
        assert agent_id in data["scope_ids"]

    async def test_active_windows_endpoint_returns_current(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/maintenance", json={
            "name": "Active Now",
            "start_time": _past(30),
            "end_time": _future(30),
            "scope": "all",
        }, headers=headers)
        await client.post("/api/v1/maintenance", json={
            "name": "Future Window",
            "start_time": _future(60),
            "end_time": _future(120),
            "scope": "all",
        }, headers=headers)
        resp = await client.get("/api/v1/maintenance/active", headers=headers)
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()]
        assert "Active Now" in names
        assert "Future Window" not in names

    async def test_active_endpoint_excludes_past_windows(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/maintenance", json={
            "name": "Already Ended",
            "start_time": _past(120),
            "end_time": _past(60),
            "scope": "all",
        }, headers=headers)
        resp = await client.get("/api/v1/maintenance/active", headers=headers)
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()]
        assert "Already Ended" not in names

    async def test_active_endpoint_excludes_inactive_flag(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/maintenance", json={
            "name": "Disabled Window",
            "start_time": _past(30),
            "end_time": _future(30),
            "scope": "all",
            "is_active": False,
        }, headers=headers)
        resp = await client.get("/api/v1/maintenance/active", headers=headers)
        assert resp.status_code == 200
        names = [w["name"] for w in resp.json()]
        assert "Disabled Window" not in names

    async def test_scope_health_checks(self, client: AsyncClient):
        headers = await _register_and_login(client)
        import uuid
        check_id = str(uuid.uuid4())
        resp = await client.post("/api/v1/maintenance", json={
            "name": "HC Window",
            "start_time": _past(5),
            "end_time": _future(5),
            "scope": "health_checks",
            "scope_ids": [check_id],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["scope"] == "health_checks"
        assert check_id in data["scope_ids"]
