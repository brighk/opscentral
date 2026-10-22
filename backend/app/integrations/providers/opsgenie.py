import httpx

from app.integrations.providers.base import ConnectionTestResult, IntegrationProvider

OPSGENIE_API_URL = "https://api.opsgenie.com/v2/alerts"


class OpsGenieProvider(IntegrationProvider):
    """OpsGenie Alert API integration."""

    display_name = "Opsgenie"

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

    async def test_connection(self) -> ConnectionTestResult:
        if not self.api_key:
            return ConnectionTestResult(False, "No API key configured")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    OPSGENIE_API_URL,
                    params={"limit": 1},
                    headers={"Authorization": f"GenieKey {self.api_key}"},
                )
        except httpx.HTTPError as e:
            return ConnectionTestResult(False, f"Could not reach Opsgenie: {e}")
        if resp.status_code == 403:
            return ConnectionTestResult(
                False,
                "Opsgenie accepted the key but it lacks Read access, which the test needs. "
                "Enable Read on the API integration, or skip the test.",
            )
        return self._result_from_response(resp)
