import json

import httpx
import pytest

from opscentral_agent.client import AgentClient
from opscentral_agent.config import config


class Server:
    """Fake OpsCentral server: records requests, answers from a route table."""

    def __init__(self, responses: dict[str, httpx.Response] | None = None):
        self.requests: list[httpx.Request] = []
        self.responses = responses or {}

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.responses.get(request.url.path, httpx.Response(200, json={"status": "ok"}))

    def body(self, index: int = -1) -> dict:
        return json.loads(self.requests[index].content)


@pytest.fixture
def server(monkeypatch) -> Server:
    monkeypatch.setattr(config, "server_url", "https://ops.example.com/")
    monkeypatch.setattr(config, "api_key", "secret-key")
    return Server()


def _client(server: Server) -> AgentClient:
    return AgentClient(transport=httpx.MockTransport(server))


def test_requests_carry_agent_key(server):
    _client(server).send_heartbeat("1.0.0", "10.0.0.2")
    request = server.requests[0]
    assert str(request.url) == "https://ops.example.com/api/v1/gateway/heartbeat"
    assert request.headers["X-Agent-Key"] == "secret-key"
    assert server.body() == {"agent_version": "1.0.0", "ip_address": "10.0.0.2"}


def test_send_metrics_and_inventory(server):
    client = _client(server)
    client.send_metrics([{"name": "cpu_percent", "value": 12.5, "unit": "%"}])
    client.send_inventory({"hostname": "web-1"}, [{"name": "nginx", "version": "1.25"}])

    assert server.body(0) == {"metrics": [{"name": "cpu_percent", "value": 12.5, "unit": "%"}]}
    assert server.body(1) == {
        "system_info": {"hostname": "web-1"},
        "software": [{"name": "nginx", "version": "1.25"}],
    }


def test_poll_actions_returns_actions(server):
    actions = [{"id": "a1", "action_type": "health_check", "parameters": None}]
    server.responses["/api/v1/gateway/actions/poll"] = httpx.Response(200, json=actions)
    assert _client(server).poll_actions() == actions


def test_poll_actions_returns_empty_list_on_server_error(server):
    server.responses["/api/v1/gateway/actions/poll"] = httpx.Response(500)
    assert _client(server).poll_actions() == []


def test_report_action_result_omits_missing_fields(server):
    client = _client(server)
    client.report_action_result("a1", "completed", result={"returncode": 0})
    client.report_action_result("a2", "failed", error="boom")

    assert server.requests[0].url.path == "/api/v1/gateway/actions/a1/result"
    assert server.body(0) == {"status": "completed", "result": {"returncode": 0}}
    assert server.body(1) == {"status": "failed", "error": "boom"}


def test_network_errors_are_logged_not_raised(monkeypatch):
    monkeypatch.setattr(config, "server_url", "https://ops.example.com")

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = AgentClient(transport=httpx.MockTransport(unreachable))
    # The agent must keep running when the server is down
    client.send_heartbeat("1.0.0")
    client.send_metrics([])
    client.send_processes([])
    client.send_inventory({})
    client.report_action_result("a1", "completed")
    assert client.poll_actions() == []
