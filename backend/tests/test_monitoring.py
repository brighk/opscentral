import pytest
from httpx import AsyncClient


async def _setup_agent_with_metrics(client: AsyncClient) -> tuple[str, str]:
    """Register user + agent, send metrics, return (token, api_key)."""
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "monitor@example.com",
            "password": "securepassword123",
            "full_name": "Monitor User",
            "company_name": "Monitor Corp",
        },
    )
    token = reg.json()["access_token"]

    agent_reg = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "monitor-server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = agent_reg.json()["api_key"]

    # Send some metrics
    await client.post(
        "/api/v1/gateway/metrics",
        json={
            "metrics": [
                {"name": "cpu_percent", "value": 45.0, "unit": "%"},
                {"name": "cpu_percent", "value": 50.0, "unit": "%"},
                {"name": "memory_percent", "value": 70.0, "unit": "%"},
            ]
        },
        headers={"X-Agent-Key": api_key},
    )

    return token, api_key


@pytest.mark.asyncio
async def test_query_metrics(client: AsyncClient):
    token, _ = await _setup_agent_with_metrics(client)
    response = await client.get(
        "/api/v1/monitoring/metrics",
        params={"metric_name": "cpu_percent"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["metric_name"] == "cpu_percent"


@pytest.mark.asyncio
async def test_status_overview(client: AsyncClient):
    token, _ = await _setup_agent_with_metrics(client)
    response = await client.get(
        "/api/v1/monitoring/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_agents"] >= 1
    assert data["metrics_last_hour"] >= 3
