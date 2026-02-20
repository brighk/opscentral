import httpx

from app.integrations.providers.base import IntegrationProvider


class ServiceNowProvider(IntegrationProvider):
    """ServiceNow Incident API integration."""

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

    async def test_connection(self) -> bool:
        url = f"{self.instance_url}/api/now/table/sys_user?sysparm_limit=1"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    url,
                    auth=(self.username, self.password),
                    headers={"Accept": "application/json"},
                    timeout=10.0,
                )
                return resp.status_code == 200
        except Exception:
            return False
