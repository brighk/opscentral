import subprocess

import pytest

from opscentral_agent import executor as executor_module
from opscentral_agent.executor import ActionExecutor


class FakeRun:
    """Records subprocess.run calls instead of running them."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.calls: list[tuple[list[str], dict]] = []
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

    def __call__(self, cmd, **kwargs):
        self.calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, self.returncode, self.stdout, self.stderr)


@pytest.fixture
def fake_run(monkeypatch) -> FakeRun:
    run = FakeRun()
    monkeypatch.setattr(executor_module.subprocess, "run", run)
    return run


def test_unknown_action_fails():
    result = ActionExecutor().execute("format_disk")
    assert result == {"status": "failed", "error": "Unknown action type: format_disk"}


def test_restart_service_requires_name(fake_run):
    result = ActionExecutor().execute("restart_service", {})
    assert result == {"status": "failed", "error": "service_name is required"}
    assert fake_run.calls == []


@pytest.mark.parametrize("name", ["--force", "nginx; reboot", "a'b", "$(id)", "", 42])
def test_restart_service_rejects_unsafe_names(fake_run, name):
    result = ActionExecutor().execute("restart_service", {"service_name": name})
    assert result["status"] == "failed"
    assert fake_run.calls == []


def test_restart_service_on_linux(fake_run, monkeypatch):
    monkeypatch.setattr(executor_module.platform, "system", lambda: "Linux")
    result = ActionExecutor().execute("restart_service", {"service_name": "nginx.service"})
    assert result["status"] == "completed"
    assert fake_run.calls[0][0] == ["sudo", "systemctl", "restart", "nginx.service"]


def test_restart_service_on_windows(fake_run, monkeypatch):
    monkeypatch.setattr(executor_module.platform, "system", lambda: "Windows")
    ActionExecutor().execute("restart_service", {"service_name": "Spooler"})
    cmd = fake_run.calls[0][0]
    assert cmd[0] == "powershell"
    assert cmd[-1] == "Restart-Service -Name 'Spooler' -ErrorAction Stop"


def test_restart_service_reports_nonzero_exit(monkeypatch):
    monkeypatch.setattr(
        executor_module.subprocess, "run", FakeRun(returncode=5, stderr="Unit not found")
    )
    result = ActionExecutor().execute("restart_service", {"service_name": "nope"})
    # The command ran; the server-side runbook engine treats returncode != 0 as failure
    assert result["status"] == "completed"
    assert result["result"]["returncode"] == 5
    assert result["result"]["stderr"] == "Unit not found"


def test_custom_script_runs_in_the_platform_shell():
    result = ActionExecutor().execute("custom_script", {"script": "echo hello"})
    assert result["status"] == "completed", result
    assert result["result"]["returncode"] == 0
    assert "hello" in result["result"]["stdout"]


def test_custom_script_timeout_is_capped(fake_run):
    ActionExecutor().execute("custom_script", {"script": "true", "timeout": 99999})
    assert fake_run.calls[0][1]["timeout"] == 300


def test_custom_script_requires_script(fake_run):
    result = ActionExecutor().execute("custom_script", {})
    assert result == {"status": "failed", "error": "script is required"}


def test_command_timeout_is_reported_as_failure(monkeypatch):
    def too_slow(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(executor_module.subprocess, "run", too_slow)
    result = ActionExecutor().execute("custom_script", {"script": "sleep 999", "timeout": 1})
    assert result["status"] == "failed"
    assert "timed out" in result["error"]


def test_collect_diagnostics():
    result = ActionExecutor().execute("collect_diagnostics")
    assert result["status"] == "completed"
    assert result["result"]["platform"]
    assert result["result"]["disk"]["total_gb"] > 0


def test_health_check_reports_unreachable_network(monkeypatch):
    def offline(*args, **kwargs):
        raise OSError("network is unreachable")

    monkeypatch.setattr("socket.create_connection", offline)
    result = ActionExecutor().execute("health_check")
    assert result["status"] == "completed"
    assert result["result"]["network"] == "unreachable"
    assert 0 <= result["result"]["memory_percent"] <= 100
