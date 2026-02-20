import httpx

from app.integrations.providers.base import IntegrationProvider

PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"


class PagerDutyProvider(IntegrationProvider):
    """PagerDuty Events API v2 integration."""

    @property
    def routing_key(self) -> str:
        return self.config.get("routing_key", "")

    async def send_alert(self, alert_data: dict) -> dict:
        payload = {
            "routing_key": self.routing_key,
            "event_action": "trigger",
            "dedup_key": alert_data.get("dedup_key", ""),
            "payload": {
                "summary": alert_data.get("summary", "OpsCentral Alert"),
                "severity": alert_data.get("severity", "warning"),
                "source": alert_data.get("source", "OpsCentral"),
                "component": alert_data.get("component", ""),
            },
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(PAGERDUTY_EVENTS_URL, json=payload, timeout=10.0)
            return {"status_code": resp.status_code, "body": resp.json()}

    async def resolve_alert(self, alert_data: dict) -> dict:
        payload = {
            "routing_key": self.routing_key,
            "event_action": "resolve",
            "dedup_key": alert_data.get("dedup_key", ""),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(PAGERDUTY_EVENTS_URL, json=payload, timeout=10.0)
            return {"status_code": resp.status_code, "body": resp.json()}

    async def test_connection(self) -> bool:
        return bool(self.routing_key)
