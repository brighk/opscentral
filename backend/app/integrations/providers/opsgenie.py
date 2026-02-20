import httpx

from app.integrations.providers.base import IntegrationProvider

OPSGENIE_API_URL = "https://api.opsgenie.com/v2/alerts"


class OpsGenieProvider(IntegrationProvider):
    """OpsGenie Alert API integration."""

    @property
    def api_key(self) -> str:
        return self.config.get("api_key", "")

    async def send_alert(self, alert_data: dict) -> dict:
        payload = {
            "message": alert_data.get("summary", "OpsCentral Alert"),
            "alias": alert_data.get("dedup_key", ""),
            "description": alert_data.get("description", ""),
            "priority": alert_data.get("priority", "P3"),
            "source": "OpsCentral",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                OPSGENIE_API_URL,
                json=payload,
                headers={"Authorization": f"GenieKey {self.api_key}"},
                timeout=10.0,
            )
            return {"status_code": resp.status_code, "body": resp.json()}

    async def resolve_alert(self, alert_data: dict) -> dict:
        alias = alert_data.get("dedup_key", "")
        url = f"{OPSGENIE_API_URL}/{alias}/close?identifierType=alias"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json={"source": "OpsCentral"},
                headers={"Authorization": f"GenieKey {self.api_key}"},
                timeout=10.0,
            )
            return {"status_code": resp.status_code, "body": resp.json()}

    async def test_connection(self) -> bool:
        return bool(self.api_key)
