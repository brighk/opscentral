import httpx

from app.integrations.providers.base import ConnectionTestResult, IntegrationProvider
from app.net import UnsafeURLError, validate_outbound_url_async


class ServiceNowProvider(IntegrationProvider):
    """ServiceNow Incident API integration."""

    display_name = "ServiceNow"

    @property
    def instance_url(self) -> str:
        return self.config.get("instance_url", "").rstrip("/")

    @property
    def username(self) -> str:
        return self.config.get("username", "")

    @property
    def password(self) -> str:
        return self.config.get("password", "")

    async def send_alert(self, alert_data: dict) -> dict:
        url = f"{self.instance_url}/api/now/table/incident"
        payload = {
            "short_description": alert_data.get("summary", "OpsCentral Alert"),
            "description": alert_data.get("description", ""),
            "urgency": alert_data.get("urgency", "2"),
            "impact": alert_data.get("impact", "2"),
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                auth=(self.username, self.password),
                headers={"Accept": "application/json"},
                timeout=10.0,
            )
            return {"status_code": resp.status_code, "body": resp.json()}

    async def resolve_alert(self, alert_data: dict) -> dict:
        # Resolve requires sys_id, simplified
        return {"detail": "ServiceNow resolve requires sys_id"}

    async def test_connection(self) -> ConnectionTestResult:
        if not (self.instance_url and self.username and self.password):
            return ConnectionTestResult(False, "instance_url, username and password are required")
        try:
            await validate_outbound_url_async(self.instance_url)
        except UnsafeURLError as e:
            return ConnectionTestResult(False, str(e))

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                # The incident table is what send_alert writes to, so check access to it
                resp = await client.get(
                    f"{self.instance_url}/api/now/table/incident",
                    params={"sysparm_limit": 1},
                    auth=(self.username, self.password),
                    headers={"Accept": "application/json"},
                )
        except httpx.HTTPError as e:
            return ConnectionTestResult(False, f"Could not reach ServiceNow: {e}")
        return self._result_from_response(resp)
