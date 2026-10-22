"""Runbook engine: real step execution, permissions, cancellation and queueing."""

import uuid

import pytest
import respx
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.remote_actions.models import RemoteAction
from app.runbooks.engine import RunbookEngine
from app.runbooks.models import RunbookExecution

# A public address literal: no DNS lookup, and passes the outbound URL guard
PUBLIC_URL = "https://93.184.215.14/hook"


async def _admin(client: AsyncClient) -> dict:
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "admin@test.com",
            "password": "testpass123",
            "full_name": "Admin",
            "company_name": "Test Corp",
        },
    )
    return {"Authorization": f"Bearer {reg.json()['access_token']}"}


async def _operator(client: AsyncClient, admin: dict) -> dict:
    await client.post(
        "/api/v1/auth/users/invite",
        json={
            "email": "op@test.com",
            "password": "operatorpass123",
            "full_name": "Operator",
            "role": "operator",
        },
        headers=admin,
    )
    login = await client.post(
        "/api/v1/auth/login", json={"email": "op@test.com", "password": "operatorpass123"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _agent(client: AsyncClient, headers: dict) -> tuple[str, str]:
    resp = await client.post(
        "/api/v1/agents/register", json={"hostname": "web-1", "os_type": "linux"}, headers=headers
    )
    data = resp.json()
    return data["agent_id"], data["api_key"]


async def _create(client: AsyncClient, headers: dict, steps: list[dict], **extra) -> dict:
    resp = await client.post(
        "/api/v1/runbooks", json={"name": "RB", "steps": steps, **extra}, headers=headers
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _steps(client: AsyncClient, headers: dict, execution_id: str) -> list[dict]:
    resp = await client.get(f"/api/v1/runbooks/executions/{execution_id}/steps", headers=headers)
    return resp.json()


def _remote_step(agent_id: str, action: str = "restart_service", **params) -> dict:
    return {
        "name": "Remote",
        "action_type": "remote_action",
        "parameters": {
            "agent_id": agent_id,
            "action": action,
            "parameters": params or {"service_name": "nginx"},
            "timeout_seconds": 60,
        },
        "on_failure": "stop",
    }


async def _approved_execution(
    client: AsyncClient, headers: dict, steps: list[dict], queued: list
) -> uuid.UUID:
    """Create a runbook and an approved (queued, not yet run) execution."""
    rb = await _create(client, headers, steps)
    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=headers)
    assert resp.json()["status"] == "approved"
    return queued[-1]


class FakeAgent:
    """Stands in for an agent: each engine poll runs one agent poll cycle via the gateway."""

    def __init__(self, client: AsyncClient, api_key: str, report: dict | None):
        self.client = client
        self.headers = {"X-Agent-Key": api_key}
        self.report = report  # None: never respond
        self.now = 0.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += 5
        actions = (
            await self.client.get("/api/v1/gateway/actions/poll", headers=self.headers)
        ).json()
        if self.report is None:
            return
        for action in actions:
            await self.client.post(
                f"/api/v1/gateway/actions/{action['id']}/result",
                json=self.report,
                headers=self.headers,
            )


# --- remote actions ---


async def test_remote_action_waits_for_agent_result(
    client: AsyncClient, db_session: AsyncSession, queued_runbooks: list
):
    headers = await _admin(client)
    agent_id, api_key = await _agent(client, headers)
    steps = [
        _remote_step(agent_id),
        {
            "name": "Check exit code",
            "action_type": "condition",
            "parameters": {"step": 0, "path": "result.returncode", "operator": "eq", "value": 0},
        },
    ]
    execution_id = await _approved_execution(client, headers, steps, queued_runbooks)

    agent = FakeAgent(
        client, api_key, {"status": "completed", "result": {"returncode": 0, "stdout": "ok"}}
    )
    await RunbookEngine(db_session, sleep=agent.sleep, clock=agent.clock).execute_runbook(
        execution_id
    )

    execution = await db_session.get(RunbookExecution, execution_id)
    assert execution is not None
    assert execution.status == "completed", execution.error
    step_results = await _steps(client, headers, str(execution_id))
    assert step_results[0]["result"]["result"] == {"returncode": 0, "stdout": "ok"}
    assert step_results[1]["result"] == {"actual": 0, "passed": True}


async def test_remote_action_nonzero_exit_fails_step(
    client: AsyncClient, db_session: AsyncSession, queued_runbooks: list
):
    headers = await _admin(client)
    agent_id, api_key = await _agent(client, headers)
    execution_id = await _approved_execution(
        client, headers, [_remote_step(agent_id)], queued_runbooks
    )

    agent = FakeAgent(client, api_key, {"status": "completed", "result": {"returncode": 3}})
    await RunbookEngine(db_session, sleep=agent.sleep, clock=agent.clock).execute_runbook(
        execution_id
    )

    execution = await db_session.get(RunbookExecution, execution_id)
    assert execution is not None
    assert execution.status == "failed"
    assert "exited with code 3" in (execution.error or "")


async def test_remote_action_times_out_and_expires_action(
    client: AsyncClient, db_session: AsyncSession, queued_runbooks: list
):
    headers = await _admin(client)
    agent_id, _ = await _agent(client, headers)
    execution_id = await _approved_execution(
        client, headers, [_remote_step(agent_id)], queued_runbooks
    )

    # No agent ever polls: the action stays pending until the 60s timeout
    fake = FakeAgent(client, "unused", None)

    async def sleep_without_agent(_seconds: float) -> None:
        fake.now += 5

    await RunbookEngine(db_session, sleep=sleep_without_agent, clock=fake.clock).execute_runbook(
        execution_id
    )

    execution = await db_session.get(RunbookExecution, execution_id)
    assert execution is not None
    assert execution.status == "failed"
    assert "did not finish within 60s" in (execution.error or "")
    action = (await db_session.execute(select(RemoteAction))).scalar_one()
    assert action.status == "expired"


async def test_cancel_while_waiting_on_agent(
    client: AsyncClient, db_session: AsyncSession, queued_runbooks: list
):
    headers = await _admin(client)
    agent_id, _ = await _agent(client, headers)
    execution_id = await _approved_execution(
        client, headers, [_remote_step(agent_id)], queued_runbooks
    )

    async def cancel_during_wait(_seconds: float) -> None:
        resp = await client.post(
            f"/api/v1/runbooks/executions/{execution_id}/cancel", headers=headers
        )
        assert resp.status_code == 200

    await RunbookEngine(db_session, sleep=cancel_during_wait).execute_runbook(execution_id)

    execution = await db_session.get(RunbookExecution, execution_id)
    assert execution is not None
    assert execution.status == "cancelled"
    action = (await db_session.execute(select(RemoteAction))).scalar_one()
    assert action.status == "expired"


async def test_engine_ignores_executions_that_are_not_approved(
    client: AsyncClient, db_session: AsyncSession, inline_runbooks
):
    headers = await _admin(client)
    rb = await _create(client, headers, [{"name": "Wait", "action_type": "delay"}])
    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=headers)
    execution_id = uuid.UUID(resp.json()["id"])
    assert resp.json()["status"] == "completed"

    # A redelivered task must not run the runbook a second time
    await RunbookEngine(db_session, poll_interval=0).execute_runbook(execution_id)
    assert len(await _steps(client, headers, str(execution_id))) == 1


# --- webhooks and conditions ---


@pytest.mark.usefixtures("inline_runbooks")
@respx.mock
async def test_webhook_and_condition(client: AsyncClient):
    headers = await _admin(client)
    route = respx.post(PUBLIC_URL).respond(200, json={"ok": True})
    rb = await _create(
        client,
        headers,
        [
            {
                "name": "Notify",
                "action_type": "webhook",
                "parameters": {"url": PUBLIC_URL, "body": {"hello": "world"}},
            },
            {
                "name": "Was 200",
                "action_type": "condition",
                "parameters": {"step": 0, "path": "status_code", "value": 200},
            },
        ],
    )

    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=headers)
    assert resp.json()["status"] == "completed", resp.json()["error"]
    assert route.calls.last.request.content == b'{"hello":"world"}'


@pytest.mark.usefixtures("inline_runbooks")
async def test_webhook_to_private_address_is_blocked(client: AsyncClient):
    headers = await _admin(client)
    rb = await _create(
        client,
        headers,
        [
            {
                "name": "Metadata",
                "action_type": "webhook",
                "parameters": {"url": "http://169.254.169.254/latest/meta-data/"},
            }
        ],
    )

    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=headers)
    assert resp.json()["status"] == "failed"
    assert "non-public address" in resp.json()["error"]


@pytest.mark.usefixtures("inline_runbooks")
@respx.mock
async def test_on_failure_continue_records_failure_and_goes_on(client: AsyncClient):
    headers = await _admin(client)
    respx.post(PUBLIC_URL).respond(500)
    rb = await _create(
        client,
        headers,
        [
            {
                "name": "Flaky",
                "action_type": "webhook",
                "parameters": {"url": PUBLIC_URL},
                "on_failure": "continue",
            },
            {"name": "Wait", "action_type": "delay"},
        ],
    )

    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=headers)
    data = resp.json()
    assert data["status"] == "completed"
    assert data["error"] == "Completed with 1 failed step(s): Flaky"
    steps = await _steps(client, headers, data["id"])
    assert [s["status"] for s in steps] == ["failed", "completed"]
    assert steps[0]["result"]["status_code"] == 500


@pytest.mark.usefixtures("inline_runbooks")
@respx.mock
async def test_failed_condition_stops_execution(client: AsyncClient):
    headers = await _admin(client)
    respx.get(PUBLIC_URL).respond(200, text="degraded")
    rb = await _create(
        client,
        headers,
        [
            {
                "name": "Health",
                "action_type": "webhook",
                "parameters": {"url": PUBLIC_URL, "method": "GET"},
            },
            {
                "name": "Body says ok",
                "action_type": "condition",
                "parameters": {"step": 0, "path": "body", "operator": "contains", "value": "ok"},
            },
            {"name": "Never runs", "action_type": "delay"},
        ],
    )

    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=headers)
    data = resp.json()
    assert data["status"] == "failed"
    assert "Condition not met" in data["error"]
    assert len(await _steps(client, headers, data["id"])) == 2


# --- validation and permissions ---


@pytest.mark.parametrize(
    ("step", "message"),
    [
        ({"action_type": "delay", "parameters": {"seconds": 99999}}, "less than or equal"),
        ({"action_type": "webhook", "parameters": {}}, "Field required"),
        (
            {
                "action_type": "remote_action",
                "parameters": {"agent_id": str(uuid.uuid4()), "action": "rm_rf"},
            },
            "action must be one of",
        ),
        ({"action_type": "condition", "parameters": {"step": 0, "path": "x"}}, "earlier step"),
        ({"action_type": "teleport", "parameters": {}}, "Input should be"),
    ],
)
async def test_invalid_steps_are_rejected(client: AsyncClient, step: dict, message: str):
    headers = await _admin(client)
    resp = await client.post(
        "/api/v1/runbooks",
        json={"name": "Bad", "steps": [{"name": "S", **step}]},
        headers=headers,
    )
    assert resp.status_code == 422
    assert message in resp.text


async def test_remote_action_agent_must_belong_to_tenant(client: AsyncClient):
    headers = await _admin(client)
    resp = await client.post(
        "/api/v1/runbooks",
        json={"name": "Other agent", "steps": [_remote_step(str(uuid.uuid4()))]},
        headers=headers,
    )
    assert resp.status_code == 400
    assert "Unknown agent" in resp.json()["detail"]


async def test_operator_cannot_add_admin_only_action(client: AsyncClient):
    admin = await _admin(client)
    operator = await _operator(client, admin)
    agent_id, _ = await _agent(client, admin)

    resp = await client.post(
        "/api/v1/runbooks",
        json={
            "name": "Script",
            "steps": [_remote_step(agent_id, "custom_script", script="id")],
        },
        headers=operator,
    )
    assert resp.status_code == 403


async def test_operator_running_admin_only_action_needs_approval(
    client: AsyncClient, queued_runbooks: list
):
    admin = await _admin(client)
    operator = await _operator(client, admin)
    agent_id, _ = await _agent(client, admin)
    rb = await _create(client, admin, [_remote_step(agent_id, "custom_script", script="id")])

    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=operator)
    assert resp.json()["status"] == "pending_approval"
    assert queued_runbooks == []

    # ...and can't strip that by editing the runbook
    resp = await client.put(
        f"/api/v1/runbooks/{rb['id']}", json={"requires_approval": False}, headers=operator
    )
    assert resp.status_code == 403

    # Admin approval queues it
    execution_id = (
        await client.get(f"/api/v1/runbooks/{rb['id']}/executions", headers=admin)
    ).json()[0]["id"]
    resp = await client.post(f"/api/v1/runbooks/executions/{execution_id}/approve", headers=admin)
    assert resp.json()["status"] == "approved"
    assert queued_runbooks == [uuid.UUID(execution_id)]


async def test_queue_unavailable_marks_execution_failed(client: AsyncClient, monkeypatch):
    from app.tasks import runbook_tasks

    def broker_down(*args, **kwargs):
        raise ConnectionError("redis unreachable")

    monkeypatch.setattr(runbook_tasks.execute_runbook_async, "delay", broker_down)
    headers = await _admin(client)
    rb = await _create(client, headers, [{"name": "Wait", "action_type": "delay"}])

    resp = await client.post(f"/api/v1/runbooks/{rb['id']}/execute", headers=headers)
    assert resp.json()["status"] == "failed"
    assert "queue is unavailable" in resp.json()["error"]
