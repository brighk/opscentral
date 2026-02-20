"""Tests for agent status history and health check log endpoints."""

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> str:
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
    response = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "test-server", "os_type": "linux"},
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.json()
    return data["agent_id"], data["api_key"]


@pytest.mark.asyncio
async def test_first_heartbeat_creates_status_log(client: AsyncClient):
    """First heartbeat should record an 'online' status transition."""
    token = await _register_and_login(client)
    agent_id, api_key = await _register_agent(client, token)

    # Send first heartbeat
    await client.post(
        "/api/v1/gateway/heartbeat",
        json={"agent_version": "0.1.0"},
        headers={"X-Agent-Key": api_key},
    )

    # Check status history
    response = await client.get(
        f"/api/v1/agents/{agent_id}/status-history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) == 1
    assert logs[0]["status"] == "online"
    assert "first time" in logs[0]["message"]


@pytest.mark.asyncio
async def test_agent_status_history_endpoint(client: AsyncClient):
    """Status history endpoint returns data in correct format."""
    token = await _register_and_login(client)
    agent_id, api_key = await _register_agent(client, token)

    # No history yet (no heartbeat sent)
    response = await client.get(
        f"/api/v1/agents/{agent_id}/status-history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_agent_status_history_not_found(client: AsyncClient):
    """Status history for non-existent agent returns 404."""
    token = await _register_and_login(client)

    response = await client.get(
        "/api/v1/agents/00000000-0000-0000-0000-000000000000/status-history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_healthcheck_logs_endpoint(client: AsyncClient):
    """Health check logs endpoint returns empty list for new check."""
    token = await _register_and_login(client)

    # Create a health check
    create_resp = await client.post(
        "/api/v1/healthchecks",
        json={"name": "Test API", "check_type": "http", "target": "https://example.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    check_id = create_resp.json()["id"]

    # Get logs (should be empty - no checks have run yet)
    response = await client.get(
        f"/api/v1/healthchecks/{check_id}/logs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json() == []
