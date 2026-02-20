import pytest
from httpx import AsyncClient


async def _setup_with_token(client: AsyncClient) -> str:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "alert@example.com",
            "password": "securepassword123",
            "full_name": "Alert User",
            "company_name": "Alert Corp",
        },
    )
    return reg.json()["access_token"]


@pytest.mark.asyncio
async def test_create_alert_rule(client: AsyncClient):
    token = await _setup_with_token(client)
    response = await client.post(
        "/api/v1/alerting/rules",
        json={
            "name": "High CPU Alert",
            "metric_name": "cpu_percent",
            "condition": "gt",
            "threshold": 80.0,
            "severity": "warning",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "High CPU Alert"
    assert data["threshold"] == 80.0


@pytest.mark.asyncio
async def test_list_alert_rules(client: AsyncClient):
    token = await _setup_with_token(client)
    await client.post(
        "/api/v1/alerting/rules",
        json={
            "name": "Test Rule",
            "metric_name": "memory_percent",
            "condition": "gt",
            "threshold": 90.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await client.get(
        "/api/v1/alerting/rules",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_update_alert_rule(client: AsyncClient):
    token = await _setup_with_token(client)
    create_resp = await client.post(
        "/api/v1/alerting/rules",
        json={
            "name": "Update Test",
            "metric_name": "cpu_percent",
            "condition": "gt",
            "threshold": 70.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    rule_id = create_resp.json()["id"]

    response = await client.put(
        f"/api/v1/alerting/rules/{rule_id}",
        json={"threshold": 85.0, "severity": "critical"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["threshold"] == 85.0
    assert response.json()["severity"] == "critical"


@pytest.mark.asyncio
async def test_delete_alert_rule(client: AsyncClient):
    token = await _setup_with_token(client)
    create_resp = await client.post(
        "/api/v1/alerting/rules",
        json={
            "name": "Delete Test",
            "metric_name": "disk_percent",
            "condition": "gt",
            "threshold": 95.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    rule_id = create_resp.json()["id"]

    response = await client.delete(
        f"/api/v1/alerting/rules/{rule_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_alerts(client: AsyncClient):
    token = await _setup_with_token(client)
    response = await client.get(
        "/api/v1/alerting/alerts",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert isinstance(data["items"], list)
