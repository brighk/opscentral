import httpx

from app.integrations.providers.base import IntegrationProvider


class JiraProvider(IntegrationProvider):
    """Jira Cloud REST API integration."""

    @property
    def base_url(self) -> str:
        return self.config.get("base_url", "").rstrip("/")

    @property
    def email(self) -> str:
        return self.config.get("email", "")

    @property
    def api_token(self) -> str:
        return self.config.get("api_token", "")

    @property
    def project_key(self) -> str:
        return self.config.get("project_key", "")

    async def send_alert(self, alert_data: dict) -> dict:
        url = f"{self.base_url}/rest/api/3/issue"
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": alert_data.get("summary", "OpsCentral Alert"),
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": alert_data.get("description", "")}],
                        }
                    ],
                },
                "issuetype": {"name": "Bug"},
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                auth=(self.email, self.api_token),
                timeout=10.0,
            )
            return {"status_code": resp.status_code, "body": resp.json()}

    async def resolve_alert(self, alert_data: dict) -> dict:
        # Jira issue resolution requires transition ID, simplified here
        return {"detail": "Jira resolve not implemented — use transitions API"}

    async def test_connection(self) -> bool:
        url = f"{self.base_url}/rest/api/3/myself"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, auth=(self.email, self.api_token), timeout=10.0)
                return resp.status_code == 200
        except Exception:
            return False
