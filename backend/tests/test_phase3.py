"""Tests for Phase 3 features: vulnerabilities, RBAC, dashboards, uptime."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.vulnerabilities.models import Vulnerability


async def _register_and_login(client: AsyncClient) -> str:
    """Helper: register user and return access token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "phase3@example.com",
            "password": "testpassword123",
            "full_name": "Phase3 User",
            "company_name": "Phase3 Corp",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "phase3@example.com",
            "password": "testpassword123",
        },
    )
    return response.json()["access_token"]


# --- Vulnerability Scanning Tests ---


@pytest.mark.asyncio
async def test_list_vulnerabilities_empty(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get(
        "/api/v1/vulnerabilities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_vulnerability_summary(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get(
        "/api/v1/vulnerabilities/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "critical" in data
    assert "high" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_vulnerability_summary_counts(client: AsyncClient, db_session: AsyncSession):
    token = await _register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}
    me = await client.get("/api/v1/auth/me", headers=headers)
    tenant_id = uuid.UUID(me.json()["tenant_id"])

    for i, severity in enumerate(["critical", "high", "high"]):
        db_session.add(
            Vulnerability(
                tenant_id=tenant_id,
                asset_id=uuid.uuid4(),
                software_name="openssl",
                cve_id=f"CVE-2026-000{i}",
                severity=severity,
                first_detected_at=datetime.now(UTC),
            )
        )
    await db_session.commit()

    response = await client.get("/api/v1/vulnerabilities/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["critical"] == 1
    assert data["high"] == 2
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_vulnerability_scans_empty(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get(
        "/api/v1/vulnerabilities/scans",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


# --- User & Access Management Tests ---


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    users = response.json()
    assert len(users) >= 1
    assert users[0]["email"] == "phase3@example.com"
    assert users[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_invite_user(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.post(
        "/api/v1/auth/users/invite",
        json={
            "email": "operator@example.com",
            "full_name": "Op User",
            "role": "operator",
            "password": "temppass123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "invited"
    assert "user_id" in data


@pytest.mark.asyncio
async def test_audit_log(client: AsyncClient):
    token = await _register_and_login(client)
    # Invite a user to generate an audit entry
    await client.post(
        "/api/v1/auth/users/invite",
        json={
            "email": "audit@example.com",
            "full_name": "Audit User",
            "role": "viewer",
            "password": "temppass123",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await client.get(
        "/api/v1/auth/audit-log",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    logs = data["items"]
    assert len(logs) >= 1
    assert logs[0]["action"] == "user.invite"


# --- Dashboard Customization Tests ---


@pytest.mark.asyncio
async def test_create_dashboard(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.post(
        "/api/v1/dashboards",
        json={
            "name": "My Dashboard",
            "description": "Test dashboard",
            "widgets": [
                {
                    "widget_type": "status_card",
                    "title": "CPU Status",
                    "config": {"metric_name": "cpu_percent"},
                    "position_x": 0,
                    "position_y": 0,
                    "width": 6,
                    "height": 4,
                },
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My Dashboard"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_and_get_dashboard(client: AsyncClient):
    token = await _register_and_login(client)

    # Create a dashboard
    create_resp = await client.post(
        "/api/v1/dashboards",
        json={"name": "List Test", "widgets": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    dashboard_id = create_resp.json()["id"]

    # List dashboards
    list_resp = await client.get(
        "/api/v1/dashboards",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # Get single dashboard
    get_resp = await client.get(
        f"/api/v1/dashboards/{dashboard_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "List Test"
    assert get_resp.json()["widgets"] == []


@pytest.mark.asyncio
async def test_add_and_remove_widget(client: AsyncClient):
    token = await _register_and_login(client)

    # Create dashboard
    create_resp = await client.post(
        "/api/v1/dashboards",
        json={"name": "Widget Test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    dashboard_id = create_resp.json()["id"]

    # Add widget
    widget_resp = await client.post(
        f"/api/v1/dashboards/{dashboard_id}/widgets",
        json={"widget_type": "alert_feed", "title": "Alerts"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert widget_resp.status_code == 200
    widget_id = widget_resp.json()["id"]

    # Verify widget exists
    get_resp = await client.get(
        f"/api/v1/dashboards/{dashboard_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(get_resp.json()["widgets"]) == 1

    # Remove widget
    del_resp = await client.delete(
        f"/api/v1/dashboards/{dashboard_id}/widgets/{widget_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_dashboard(client: AsyncClient):
    token = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/dashboards",
        json={"name": "Delete Me"},
        headers={"Authorization": f"Bearer {token}"},
    )
    dashboard_id = create_resp.json()["id"]

    del_resp = await client.delete(
        f"/api/v1/dashboards/{dashboard_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 200


# --- Uptime Monitoring Tests ---


@pytest.mark.asyncio
async def test_uptime_stats_empty(client: AsyncClient):
    token = await _register_and_login(client)
    response = await client.get(
        "/api/v1/uptime/stats",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_uptime_stats_with_check(client: AsyncClient):
    token = await _register_and_login(client)

    # Create a health check first
    await client.post(
        "/api/v1/healthchecks",
        json={"name": "Uptime API", "check_type": "http", "target": "https://api.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    response = await client.get(
        "/api/v1/uptime/stats?period=24h",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    stats = response.json()
    assert len(stats) == 1
    assert stats[0]["name"] == "Uptime API"
    assert stats[0]["total_checks"] == 0  # No logs yet


@pytest.mark.asyncio
async def test_public_status_page_not_found(client: AsyncClient):
    response = await client.get("/api/v1/status/nonexistent-tenant")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_public_status_page(client: AsyncClient):
    token = await _register_and_login(client)

    # Create a health check
    await client.post(
        "/api/v1/healthchecks",
        json={"name": "Web App", "check_type": "http", "target": "https://app.example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Access public status page using tenant slug
    response = await client.get("/api/v1/status/phase3-corp")
    assert response.status_code == 200
    data = response.json()
    assert data["organization"] == "Phase3 Corp"
    assert data["overall_status"] in ["operational", "degraded", "major_outage"]
    assert len(data["services"]) == 1
    assert data["services"][0]["name"] == "Web App"
