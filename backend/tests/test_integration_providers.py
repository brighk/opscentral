"""Integration connection tests and the outbound URL guard."""

import pytest
import respx
from httpx import AsyncClient

from app.config import settings
from app.net import UnsafeURLError, validate_outbound_url

JIRA_URL = "https://93.184.215.14"  # public address literal, no DNS needed


async def _admin(client: AsyncClient) -> dict:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@test.com",
            "password": "testpass123",
            "full_name": "Admin",
            "company_name": "Test Corp",
        },
    )
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _test(client: AsyncClient, provider: str, config: dict):
    headers = await _admin(client)
    created = await client.post(
        "/api/v1/integrations",
        json={"provider": provider, "name": provider, "config": config},
        headers=headers,
    )
    return await client.post(f"/api/v1/integrations/{created.json()['id']}/test", headers=headers)


# --- providers ---


@respx.mock
async def test_opsgenie_rejected_key(client: AsyncClient):
    respx.get("https://api.opsgenie.com/v2/alerts").respond(401)
    resp = await _test(client, "opsgenie", {"api_key": "bad"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Opsgenie rejected the credentials (HTTP 401)"


@respx.mock
async def test_opsgenie_key_without_read_access(client: AsyncClient):
    respx.get("https://api.opsgenie.com/v2/alerts").respond(403)
    resp = await _test(client, "opsgenie", {"api_key": "write-only"})
    assert resp.status_code == 400
    assert "lacks Read access" in resp.json()["detail"]


async def test_pagerduty_checks_key_format_without_paging(client: AsyncClient):
    # respx is not active: any real HTTP request here would error out
    resp = await _test(client, "pagerduty", {"routing_key": "too-short"})
    assert resp.status_code == 400
    assert "32 letters and digits" in resp.json()["detail"]


async def test_pagerduty_valid_key_format(client: AsyncClient):
    resp = await _test(client, "pagerduty", {"routing_key": "a" * 32})
    assert resp.status_code == 200
    assert "can't verify a key without creating an incident" in resp.json()["detail"]


@respx.mock
async def test_jira_success_reports_user_and_project(client: AsyncClient):
    respx.get(f"{JIRA_URL}/rest/api/3/myself").respond(200, json={"displayName": "Ops Bot"})
    respx.get(f"{JIRA_URL}/rest/api/3/project/OPS").respond(200, json={"key": "OPS"})
    resp = await _test(
        client,
        "jira",
        {"base_url": JIRA_URL, "email": "a@b.c", "api_token": "t", "project_key": "OPS"},
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "Signed in as Ops Bot; project 'OPS' is accessible"


@respx.mock
async def test_jira_missing_project(client: AsyncClient):
    respx.get(f"{JIRA_URL}/rest/api/3/myself").respond(200, json={"displayName": "Ops Bot"})
    respx.get(f"{JIRA_URL}/rest/api/3/project/NOPE").respond(404)
    resp = await _test(
        client,
        "jira",
        {"base_url": JIRA_URL, "email": "a@b.c", "api_token": "t", "project_key": "NOPE"},
    )
    assert resp.status_code == 400
    assert "project 'NOPE' wasn't found" in resp.json()["detail"]


async def test_jira_private_url_blocked(client: AsyncClient):
    resp = await _test(
        client,
        "jira",
        {
            "base_url": "http://127.0.0.1:8080",
            "email": "a@b.c",
            "api_token": "t",
            "project_key": "X",
        },
    )
    assert resp.status_code == 400
    assert "non-public address" in resp.json()["detail"]


@respx.mock
async def test_servicenow_checks_incident_table(client: AsyncClient):
    route = respx.get("https://93.184.215.14/api/now/table/incident").respond(200, json={})
    resp = await _test(
        client,
        "servicenow",
        {"instance_url": "https://93.184.215.14", "username": "u", "password": "p"},
    )
    assert resp.status_code == 200
    assert route.called


# --- outbound URL guard ---


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/",  # carrier-grade NAT
        "http://[::1]/",
        "http://[::ffff:127.0.0.1]/",
        "http://0.0.0.0/",
    ],
)
def test_private_addresses_are_rejected(url: str):
    with pytest.raises(UnsafeURLError, match="non-public address"):
        validate_outbound_url(url)


@pytest.mark.parametrize("url", ["ftp://93.184.215.14/", "file:///etc/passwd", "https:///nohost"])
def test_bad_schemes_and_hosts_are_rejected(url: str):
    with pytest.raises(UnsafeURLError):
        validate_outbound_url(url)


def test_public_address_is_allowed():
    validate_outbound_url("https://93.184.215.14/hook")


def test_private_targets_can_be_allowed_for_self_hosting(monkeypatch):
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_NETWORK_TARGETS", True)
    validate_outbound_url("http://10.0.0.5/")
