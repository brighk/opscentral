import pytest

from opscentral_agent import main
from opscentral_agent.config import config


class FakeClient:
    def __init__(self, actions: list[dict] | None = None):
        self.actions = actions or []
        self.polled = False
        self.reports: list[dict] = []
        self.metrics: list[dict] = []
        self.heartbeats: list[str] = []
        self.processes: list[dict] = []

    def poll_actions(self) -> list[dict]:
        self.polled = True
        return self.actions

    def report_action_result(self, action_id, status, result=None, error=None):
        self.reports.append({"id": action_id, "status": status, "result": result, "error": error})

    def send_metrics(self, metrics):
        self.metrics = metrics

    def send_heartbeat(self, agent_version, ip_address=None):
        self.heartbeats.append(agent_version)

    def send_processes(self, processes):
        self.processes = processes


@pytest.fixture(autouse=True)
def remote_actions_enabled(monkeypatch):
    monkeypatch.setattr(config, "enable_remote_actions", True)
    monkeypatch.setattr(config, "allowed_actions", ["collect_diagnostics", "health_check"])


def test_disabled_remote_actions_do_not_poll(monkeypatch):
    monkeypatch.setattr(config, "enable_remote_actions", False)
    client = FakeClient()
    main.poll_and_execute_actions(client)  # type: ignore[arg-type]
    assert client.polled is False


def test_allowed_action_is_executed_and_reported():
    client = FakeClient([{"id": "a1", "action_type": "collect_diagnostics", "parameters": {}}])
    main.poll_and_execute_actions(client)  # type: ignore[arg-type]

    assert len(client.reports) == 1
    report = client.reports[0]
    assert report["id"] == "a1"
    assert report["status"] == "completed"
    assert "platform" in report["result"]


def test_disallowed_action_is_refused_without_running(monkeypatch):
    def must_not_run(*args, **kwargs):
        raise AssertionError("executor ran a disallowed action")

    monkeypatch.setattr("opscentral_agent.executor.ActionExecutor.execute", must_not_run)
    client = FakeClient(
        [{"id": "a1", "action_type": "custom_script", "parameters": {"script": "id"}}]
    )
    main.poll_and_execute_actions(client)  # type: ignore[arg-type]

    assert client.reports == [
        {
            "id": "a1",
            "status": "failed",
            "result": None,
            "error": "Action type 'custom_script' is not allowed",
        }
    ]


def test_action_without_id_is_ignored():
    client = FakeClient([{"action_type": "health_check"}])
    main.poll_and_execute_actions(client)  # type: ignore[arg-type]
    assert client.reports == []


def test_collect_and_send_metrics():
    client = FakeClient()
    main.collect_and_send_metrics(client)  # type: ignore[arg-type]

    names = {m["name"] for m in client.metrics}
    assert {"cpu_percent", "memory_percent"} <= names
    assert client.heartbeats == [main.__version__]
    assert client.processes, "expected at least one running process"
