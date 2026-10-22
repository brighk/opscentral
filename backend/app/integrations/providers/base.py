from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx


@dataclass
class ConnectionTestResult:
    ok: bool
    detail: str


class IntegrationProvider(ABC):
    """Abstract base class for external integration providers."""

    display_name = "Provider"

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    async def send_alert(self, alert_data: dict) -> dict:
        """Send an alert/incident to the provider."""
        ...

    @abstractmethod
    async def resolve_alert(self, alert_data: dict) -> dict:
        """Resolve an alert/incident in the provider."""
        ...

    @abstractmethod
    async def test_connection(self) -> ConnectionTestResult:
        """Check the configuration against the provider, as far as its API allows."""
        ...

    def _result_from_response(self, resp: httpx.Response) -> ConnectionTestResult:
        if resp.status_code == 200:
            return ConnectionTestResult(True, f"Connected to {self.display_name}")
        if resp.status_code in (401, 403):
            return ConnectionTestResult(
                False, f"{self.display_name} rejected the credentials (HTTP {resp.status_code})"
            )
        return ConnectionTestResult(False, f"{self.display_name} returned HTTP {resp.status_code}")
