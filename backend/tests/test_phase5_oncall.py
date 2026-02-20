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


class TestOnCall:
    async def test_create_schedule(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.post("/api/v1/oncall/schedules", json={
            "name": "Primary On-Call",
            "rotation_type": "weekly",
            "participants": ["user-1", "user-2", "user-3"],
            "handoff_time": "09:00",
            "handoff_day": 1,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Primary On-Call"
        assert data["rotation_type"] == "weekly"
        assert len(data["participants"]) == 3

    async def test_list_schedules(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/oncall/schedules", json={
            "name": "Test Schedule",
            "participants": ["user-1"],
        }, headers=headers)
        resp = await client.get("/api/v1/oncall/schedules", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_current_oncall(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post("/api/v1/oncall/schedules", json={
            "name": "Current Test",
            "rotation_type": "daily",
            "participants": ["user-a", "user-b"],
        }, headers=headers)
        sched_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/oncall/schedules/{sched_id}/current", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] in ["user-a", "user-b"]
        assert data["schedule_name"] == "Current Test"

    async def test_delete_schedule(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post("/api/v1/oncall/schedules", json={
            "name": "Delete Me",
            "participants": [],
        }, headers=headers)
        sched_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/oncall/schedules/{sched_id}", headers=headers)
        assert resp.status_code == 200

    async def test_create_override(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post("/api/v1/oncall/schedules", json={
            "name": "Override Test",
            "participants": ["user-1"],
        }, headers=headers)
        sched_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/oncall/schedules/{sched_id}/overrides", json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "start_time": "2026-02-20T00:00:00Z",
            "end_time": "2026-02-21T00:00:00Z",
            "reason": "Vacation coverage",
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["reason"] == "Vacation coverage"

    async def test_create_escalation_policy(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.post("/api/v1/oncall/policies", json={
            "name": "Default Escalation",
            "description": "Standard escalation flow",
            "steps": [
                {"delay_minutes": 5, "targets": [{"type": "user", "id": "user-1"}]},
                {"delay_minutes": 15, "targets": [{"type": "user", "id": "user-2"}]},
            ],
            "repeat_count": 2,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Default Escalation"
        assert len(data["steps"]) == 2
        assert data["repeat_count"] == 2

    async def test_list_policies(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post("/api/v1/oncall/policies", json={
            "name": "Test Policy",
            "steps": [],
        }, headers=headers)
        resp = await client.get("/api/v1/oncall/policies", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_delete_policy(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post("/api/v1/oncall/policies", json={
            "name": "Delete Policy",
            "steps": [],
        }, headers=headers)
        pol_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/oncall/policies/{pol_id}", headers=headers)
        assert resp.status_code == 200

    async def test_whoami(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.get("/api/v1/oncall/whoami", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
