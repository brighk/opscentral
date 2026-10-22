from opscentral_agent.config import AgentConfig


def test_defaults():
    config = AgentConfig()
    assert config.server_url == "http://localhost:8000"
    assert config.api_key == ""
    assert config.collect_interval == 60


def test_load_from_file(tmp_path):
    path = tmp_path / "agent.yml"
    path.write_text(
        "server_url: https://ops.example.com\n"
        "api_key: abc123\n"
        "collect_interval: 15\n"
        "enable_remote_actions: false\n"
        "allowed_actions: [health_check]\n"
    )
    config = AgentConfig()
    config.load_from_file(str(path))

    assert config.server_url == "https://ops.example.com"
    assert config.api_key == "abc123"
    assert config.collect_interval == 15
    assert config.enable_remote_actions is False
    assert config.allowed_actions == ["health_check"]
    # Keys missing from the file keep their defaults
    assert config.inventory_interval == 300


def test_missing_or_empty_file_keeps_defaults(tmp_path):
    config = AgentConfig()
    config.load_from_file(str(tmp_path / "does-not-exist.yml"))
    assert config.server_url == "http://localhost:8000"

    empty = tmp_path / "empty.yml"
    empty.write_text("")
    config.load_from_file(str(empty))
    assert config.server_url == "http://localhost:8000"


def test_env_overrides_file(tmp_path, monkeypatch):
    path = tmp_path / "agent.yml"
    path.write_text("server_url: https://from-file\napi_key: file-key\n")
    monkeypatch.setenv("OC_API_KEY", "env-key")
    monkeypatch.setenv("OC_COLLECT_INTERVAL", "5")

    config = AgentConfig()
    config.load_from_file(str(path))
    config.load_from_env()

    assert config.server_url == "https://from-file"
    assert config.api_key == "env-key"
    assert config.collect_interval == 5


def test_remote_actions_env_flag(monkeypatch):
    for value, expected in [("false", False), ("0", False), ("TRUE", True), ("yes", True)]:
        monkeypatch.setenv("OC_ENABLE_REMOTE_ACTIONS", value)
        config = AgentConfig()
        config.load_from_env()
        assert config.enable_remote_actions is expected, value
