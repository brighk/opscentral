from abc import ABC, abstractmethod


class IntegrationProvider(ABC):
    """Abstract base class for external integration providers."""

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
    async def test_connection(self) -> bool:
        """Test that the integration configuration is valid."""
        ...
