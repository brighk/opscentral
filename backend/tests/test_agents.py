import pytest
from httpx import AsyncClient


async def _register_and_get_token(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "agent_test@example.com",
            "password": "securepassword123",
            "full_name": "Agent Tester",
            "company_name": "Agent Corp",
        },
    )
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_register_agent(client: AsyncClient):
    token = await _register_and_get_token(client)
    response = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "test-server-01", "os_type": "linux", "os_version": "Ubuntu 22.04"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "agent_id" in data
    assert "api_key" in data


@pytest.mark.asyncio
async def test_list_agents(client: AsyncClient):
    token = await _register_and_get_token(client)
    # Register an agent first
    await client.post(
        "/api/v1/agents/register",
        json={"hostname": "list-test-server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response = await client.get(
        "/api/v1/agents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    agents = data["items"]
    assert len(agents) >= 1


@pytest.mark.asyncio
async def test_agent_heartbeat(client: AsyncClient):
    token = await _register_and_get_token(client)
    reg = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "heartbeat-server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = reg.json()["api_key"]

    response = await client.post(
        "/api/v1/gateway/heartbeat",
        json={"agent_version": "0.1.0", "ip_address": "192.168.1.100"},
        headers={"X-Agent-Key": api_key},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_agent_metrics_ingest(client: AsyncClient):
    token = await _register_and_get_token(client)
    reg = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "metrics-server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = reg.json()["api_key"]

    response = await client.post(
        "/api/v1/gateway/metrics",
        json={
            "metrics": [
                {"name": "cpu_percent", "value": 45.2, "unit": "%"},
                {"name": "memory_percent", "value": 62.1, "unit": "%"},
            ]
        },
        headers={"X-Agent-Key": api_key},
    )
    assert response.status_code == 200
    assert response.json()["ingested"] == 2


@pytest.mark.asyncio
async def test_agent_inventory(client: AsyncClient):
    token = await _register_and_get_token(client)
    reg = await client.post(
        "/api/v1/agents/register",
        json={"hostname": "inventory-server"},
        headers={"Authorization": f"Bearer {token}"},
    )
    api_key = reg.json()["api_key"]

    response = await client.post(
        "/api/v1/gateway/inventory",
        json={
            "system_info": {
                "hostname": "inventory-server",
                "os_type": "linux",
                "os_version": "Ubuntu 22.04",
                "cpu_model": "Intel i7-12700K",
                "cpu_cores": 12,
                "ram_total_gb": 32.0,
                "disk_total_gb": 512.0,
                "ip_addresses": ["192.168.1.100"],
                "mac_addresses": ["00:11:22:33:44:55"],
            },
            "software": [
                {"name": "nginx", "version": "1.24.0", "publisher": "Nginx Inc"},
                {"name": "python", "version": "3.12.0", "publisher": "Python Software Foundation"},
            ],
        },
        headers={"X-Agent-Key": api_key},
    )
    assert response.status_code == 200
    assert "asset_id" in response.json()
