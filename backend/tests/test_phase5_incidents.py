from httpx import AsyncClient


async def _register_and_login(client: AsyncClient, email: str = "admin@test.com"):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "testpass123",
            "full_name": "Test Admin",
            "company_name": "Test Corp",
        },
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


class TestIncidents:
    async def test_create_incident(self, client: AsyncClient):
        headers = await _register_and_login(client)
        resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Database outage",
                "description": "Production DB is unreachable",
                "severity": "critical",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Database outage"
        assert data["severity"] == "critical"
        assert data["status"] == "open"

    async def test_list_incidents(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post(
            "/api/v1/incidents",
            json={
                "title": "Test Incident",
                "severity": "warning",
            },
            headers=headers,
        )
        resp = await client.get("/api/v1/incidents", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_list_incidents_with_filter(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post(
            "/api/v1/incidents",
            json={
                "title": "Open Incident",
                "severity": "warning",
            },
            headers=headers,
        )
        resp = await client.get("/api/v1/incidents?status=open", headers=headers)
        assert resp.status_code == 200
        for inc in resp.json():
            assert inc["status"] == "open"

    async def test_get_incident(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Get Me",
                "severity": "info",
            },
            headers=headers,
        )
        inc_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/incidents/{inc_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Get Me"

    async def test_resolve_incident(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Resolve Me",
                "severity": "warning",
            },
            headers=headers,
        )
        inc_id = create_resp.json()["id"]

        resp = await client.post(f"/api/v1/incidents/{inc_id}/resolve", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "resolved"
        assert resp.json()["resolved_at"] is not None

    async def test_add_update(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Update Me",
                "severity": "critical",
            },
            headers=headers,
        )
        inc_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/incidents/{inc_id}/updates",
            json={
                "message": "Investigating root cause",
                "update_type": "status_change",
                "new_status": "investigating",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "Investigating root cause"

    async def test_list_updates(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Timeline Test",
                "severity": "warning",
            },
            headers=headers,
        )
        inc_id = create_resp.json()["id"]

        await client.post(
            f"/api/v1/incidents/{inc_id}/updates",
            json={
                "message": "First update",
            },
            headers=headers,
        )

        resp = await client.get(f"/api/v1/incidents/{inc_id}/updates", headers=headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_get_stats(self, client: AsyncClient):
        headers = await _register_and_login(client)
        await client.post(
            "/api/v1/incidents",
            json={
                "title": "Stats Test",
                "severity": "warning",
            },
            headers=headers,
        )

        resp = await client.get("/api/v1/incidents/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert "open" in data
        assert "mttr_hours" in data

    async def test_create_postmortem(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Postmortem Test",
                "severity": "critical",
            },
            headers=headers,
        )
        inc_id = create_resp.json()["id"]

        resp = await client.post(
            f"/api/v1/incidents/{inc_id}/postmortem",
            json={
                "summary": "Root cause was a config change",
                "root_cause": "Bad deploy",
                "impact": "30 min downtime",
                "lessons_learned": "Add canary deploys",
                "action_items": "Implement blue-green deployment",
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["summary"] == "Root cause was a config change"

    async def test_duplicate_postmortem_fails(self, client: AsyncClient):
        headers = await _register_and_login(client)
        create_resp = await client.post(
            "/api/v1/incidents",
            json={
                "title": "Dup PM Test",
                "severity": "warning",
            },
            headers=headers,
        )
        inc_id = create_resp.json()["id"]

        await client.post(
            f"/api/v1/incidents/{inc_id}/postmortem",
            json={
                "summary": "First postmortem",
            },
            headers=headers,
        )

        resp = await client.post(
            f"/api/v1/incidents/{inc_id}/postmortem",
            json={
                "summary": "Second postmortem",
            },
            headers=headers,
        )
        assert resp.status_code == 409
