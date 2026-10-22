import httpx

from app.integrations.providers.base import ConnectionTestResult, IntegrationProvider
from app.net import UnsafeURLError, validate_outbound_url_async


class JiraProvider(IntegrationProvider):
    """Jira Cloud REST API integration."""

    display_name = "Jira"

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
                            "content": [
                                {"type": "text", "text": alert_data.get("description", "")}
                            ],
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

    async def test_connection(self) -> ConnectionTestResult:
        if not (self.base_url and self.email and self.api_token and self.project_key):
            return ConnectionTestResult(
                False, "base_url, email, api_token and project_key are all required"
            )
        try:
            await validate_outbound_url_async(self.base_url)
        except UnsafeURLError as e:
            return ConnectionTestResult(False, str(e))

        auth = (self.email, self.api_token)
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
                resp = await client.get(f"{self.base_url}/rest/api/3/myself", auth=auth)
                if resp.status_code != 200:
                    return self._result_from_response(resp)
                user = resp.json().get("displayName") or self.email

                resp = await client.get(
                    f"{self.base_url}/rest/api/3/project/{self.project_key}", auth=auth
                )
        except httpx.HTTPError as e:
            return ConnectionTestResult(False, f"Could not reach Jira: {e}")
        if resp.status_code == 404:
            return ConnectionTestResult(
                False, f"Signed in as {user}, but project {self.project_key!r} wasn't found"
            )
        if resp.status_code != 200:
            return self._result_from_response(resp)
        return ConnectionTestResult(
            True, f"Signed in as {user}; project {self.project_key!r} is accessible"
        )
