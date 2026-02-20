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


class TestReports:
    async def test_list_reports_empty(self, client: AsyncClient):
        headers = await _register_and_login(client)

        resp = await client.get("/api/v1/reports", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_generate_report_queued(self, client: AsyncClient):
        headers = await _register_and_login(client)

        resp = await client.post("/api/v1/reports", json={
            "report_type": "security_posture",
            "format": "pdf",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "security_posture"
        assert data["status"] in ("generating", "queued")

    async def test_compliance_score_empty(self, client: AsyncClient):
        headers = await _register_and_login(client)

        resp = await client.get("/api/v1/reports/compliance", headers=headers)
        assert resp.status_code == 200
        # No scores calculated yet, should return null
        assert resp.json() is None

    async def test_create_schedule(self, client: AsyncClient):
        headers = await _register_and_login(client)

        resp = await client.post("/api/v1/reports/schedules", json={
            "report_type": "security_posture",
            "frequency": "weekly",
            "recipients": ["admin@test.com"],
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["report_type"] == "security_posture"
        assert data["frequency"] == "weekly"
        assert data["is_active"] is True
        assert data["next_run_at"] is not None

    async def test_delete_schedule(self, client: AsyncClient):
        headers = await _register_and_login(client)

        # Create
        create_resp = await client.post("/api/v1/reports/schedules", json={
            "report_type": "asset_inventory",
            "frequency": "monthly",
        }, headers=headers)
        schedule_id = create_resp.json()["id"]

        # Delete
        resp = await client.delete(f"/api/v1/reports/schedules/{schedule_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Verify deleted
        list_resp = await client.get("/api/v1/reports/schedules", headers=headers)
        assert len(list_resp.json()) == 0

    async def test_viewer_cannot_generate(self, client: AsyncClient):
        admin_headers = await _register_and_login(client)
        viewer_headers = await _create_viewer(client, admin_headers)

        resp = await client.post("/api/v1/reports", json={
            "report_type": "security_posture",
            "format": "pdf",
        }, headers=viewer_headers)
        assert resp.status_code == 403
