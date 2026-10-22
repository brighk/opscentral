import os
import platform
from pathlib import Path

import yaml


class AgentConfig:
    def __init__(self):
        self.server_url: str = "http://localhost:8000"
        self.api_key: str = ""
        self.collect_interval: int = 60
        self.inventory_interval: int = 300
        self.action_poll_interval: int = 10
        self.enable_remote_actions: bool = True
        self.allowed_actions: list[str] = [
            "restart_service",
            "collect_diagnostics",
            "update_agent",
            "health_check",
            "custom_script",
        ]
        self.log_level: str = "INFO"

    def _default_config_path(self) -> str:
        if platform.system() == "Windows":
            return r"C:\ProgramData\OpsCentral\agent.yml"
        return "/etc/opscentral/agent.yml"

    def load_from_file(self, path: str | None = None):
        p = Path(path or self._default_config_path())
        if p.exists():
            with open(p) as f:
                data = yaml.safe_load(f) or {}
            self.server_url = data.get("server_url", self.server_url)
            self.api_key = data.get("api_key", self.api_key)
            self.collect_interval = data.get("collect_interval", self.collect_interval)
            self.inventory_interval = data.get("inventory_interval", self.inventory_interval)
            self.log_level = data.get("log_level", self.log_level)
            self.action_poll_interval = data.get("action_poll_interval", self.action_poll_interval)
            self.enable_remote_actions = data.get(
                "enable_remote_actions", self.enable_remote_actions
            )
            self.allowed_actions = data.get("allowed_actions", self.allowed_actions)

    def load_from_env(self):
        self.server_url = os.environ.get("OC_SERVER_URL", self.server_url)
        self.api_key = os.environ.get("OC_API_KEY", self.api_key)
        self.collect_interval = int(os.environ.get("OC_COLLECT_INTERVAL", self.collect_interval))
        self.inventory_interval = int(
            os.environ.get("OC_INVENTORY_INTERVAL", self.inventory_interval)
        )
        self.log_level = os.environ.get("OC_LOG_LEVEL", self.log_level)
        self.action_poll_interval = int(
            os.environ.get("OC_ACTION_POLL_INTERVAL", self.action_poll_interval)
        )
        self.enable_remote_actions = os.environ.get(
            "OC_ENABLE_REMOTE_ACTIONS", str(self.enable_remote_actions)
        ).lower() in ("true", "1", "yes")


config = AgentConfig()
