"""Tests for Phase 2 features: processes, health checks, notification channels."""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
    """Helper: register user and return access token."""
    await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User",
        "company_name": "Test Corp",
    })
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "testpassword123",
    })
    return response.json()["access_token"]


async def _register_agent(client: AsyncClient, token: str) -> tuple[str, str]:
    """Helper: register an agent and return (agent_id, api_key)."""
    response = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "test-server", "os_type": "linux"},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    return data["agent_id"], data["api_key"]


# --- Process Monitoring Tests ---

@pytest.mark.asyncio
async def test_submit_processes(client: AsyncClient):
    token = await _register_and_login(client)
    agent_id, api_key = await _register_agent(client, token)

    response = await client.post(
        "/api/v1/gateway/processes",
        json={
            "processes": [
                {
                    "pid": 1234,
                    "name": "python",
                    "cpu_percent": 25.5,
                    "memory_percent": 12.3,
                    "memory_mb": 256.0,
                    "status": "running",
                    "username": "root",
                    "num_threads": 4,
                    "command": "python main.py",
                },
                {
                    "pid": 5678,
                    "name": "nginx",
                    "cpu_percent": 1.2,
                    "memory_percent": 3.5,
                    "memory_mb": 64.0,
                    "status": "sleeping",
                    "username": "www-data",
                    "num_threads": 2,
                    "command": "nginx: master process",
                },
            ]
        },
        headers={"X-Agent-Key": api_key},
    )
    assert response.status_code == 200
    assert response.json()["ingested"] == 2


@pytest.mark.asyncio
async def test_query_processes(client: AsyncClient):
    token = await _register_and_login(client)
    agent_id, api_key = await _register_agent(client, token)

    # Submit some processes
    await client.post(
        "/api/v1/gateway/processes",
        json={
            "processes": [
                {"pid": 1, "name": "init", "cpu_percent": 0, "memory_percent": 0.1},
            ]
        },
        headers={"X-Agent-Key": api_key},
    )

    # Query processes
    response = await client.get(
        "/api/v1/monitoring/processes",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "init"


# --- Notification Channel Tests ---

@pytest.mark.asyncio
async def test_create_notification_channel(client: AsyncClient):
    token = await _register_and_login(client)

    response = await client.post(
        "/api/v1/notifications/channels",
        json={
            "name": "Ops Slack",
            "channel_type": "slack",
            "config": {"webhook_url": "https://hooks.slack.com/services/test"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Ops Slack"
    assert data["channel_type"] == "slack"
    assert data["is_enabled"] is True


@pytest.mark.asyncio
async def test_list_notification_channels(client: AsyncClient):
    token = await _register_and_login(client)

    # Create two channels
    for name, ctype in [("Slack", "slack"), ("Teams", "teams")]:
        await client.post(
            "/api/v1/notifications/channels",
            json={"name": name, "channel_type": ctype, "config": {"webhook_url": "https://test"}},
            headers={"Authorization": f"Bearer {token}"},
        )

    response = await client.get(
        "/api/v1/notifications/channels",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 2


@pytest.mark.asyncio
async def test_delete_notification_channel(client: AsyncClient):
    token = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/notifications/channels",
        json={"name": "Temp", "channel_type": "webhook", "config": {"url": "https://test"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    channel_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/v1/notifications/channels/{channel_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 200

    list_resp = await client.get(
        "/api/v1/notifications/channels",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_resp.json()) == 0


# --- Health Check Tests ---

@pytest.mark.asyncio
async def test_create_health_check(client: AsyncClient):
    token = await _register_and_login(client)

    response = await client.post(
        "/api/v1/healthchecks",
        json={
            "name": "Production API",
            "check_type": "http",
            "target": "https://api.example.com/health",
            "interval_seconds": 60,
            "expected_status": 200,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Production API"
    assert data["check_type"] == "http"
    assert data["status"] == "unknown"


@pytest.mark.asyncio
async def test_list_health_checks(client: AsyncClient):
    token = await _register_and_login(client)

    for name, check_type, target in [
        ("API", "http", "https://api.example.com"),
        ("DB", "tcp", "db.example.com:5432"),
        ("DNS", "dns", "example.com"),
    ]:
        await client.post(
            "/api/v1/healthchecks",
            json={"name": name, "check_type": check_type, "target": target},
            headers={"Authorization": f"Bearer {token}"},
        )

    response = await client.get(
        "/api/v1/healthchecks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 3


@pytest.mark.asyncio
async def test_delete_health_check(client: AsyncClient):
    token = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/healthchecks",
        json={"name": "Temp Check", "check_type": "dns", "target": "example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    check_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/v1/healthchecks/{check_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert delete_resp.status_code == 200

    list_resp = await client.get(
        "/api/v1/healthchecks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(list_resp.json()) == 0
