import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent
from app.net import UnsafeURLError, validate_outbound_url_async
from app.remote_actions.models import RemoteAction
from app.runbooks.models import Runbook, RunbookExecution, RunbookStepExecution
from app.runbooks.schemas import (
    STEP_PARAM_MODELS,
    ConditionStepParams,
    DelayStepParams,
    RemoteActionStepParams,
    WebhookStepParams,
)

logger = logging.getLogger(__name__)

# Remote action statuses after which the agent will not report again
TERMINAL_ACTION_STATUSES = ("completed", "failed", "expired")


class StepError(Exception):
    """A step failed. `result` is still recorded on the step execution."""

    def __init__(self, message: str, result: dict | None = None):
        super().__init__(message)
        self.result = result


class ExecutionCancelled(Exception):
    pass


class RunbookEngine:
    def __init__(
        self,
        db: AsyncSession,
        *,
        poll_interval: float = 2.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.db = db
        self.poll_interval = poll_interval
        self._sleep = sleep
        self._clock = clock

    async def execute_runbook(self, execution_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(RunbookExecution).where(RunbookExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        # Only approved executions run; this also makes a redelivered task a no-op
        if not execution or execution.status != "approved":
            return

        result = await self.db.execute(
            select(Runbook).where(
                Runbook.id == execution.runbook_id,
                Runbook.tenant_id == execution.tenant_id,
            )
        )
        runbook = result.scalar_one_or_none()
        if not runbook:
            await self._finish(execution, "failed", "Runbook not found")
            return

        execution.status = "running"
        execution.started_at = datetime.now(UTC)
        await self.db.commit()
        await self._notify(execution, runbook, "runbook.started")

        steps = runbook.steps if isinstance(runbook.steps, list) else []
        results: list[dict | None] = []
        failed_steps: list[str] = []

        for i, step in enumerate(steps):
            step_name = step.get("name", f"Step {i + 1}")
            on_failure = step.get("on_failure", "stop")

            if await self._is_cancelled(execution):
                return

            step_exec = RunbookStepExecution(
                execution_id=execution.id,
                step_index=i,
                step_name=step_name,
                status="running",
                started_at=datetime.now(UTC),
            )
            self.db.add(step_exec)
            await self.db.commit()

            try:
                result_data = await self._execute_step(execution, step, results)
            except ExecutionCancelled:
                step_exec.status = "failed"
                step_exec.error = "Execution cancelled"
                step_exec.completed_at = datetime.now(UTC)
                await self.db.commit()
                return
            except Exception as e:
                if not isinstance(e, StepError):
                    logger.exception(f"Runbook {runbook.id} step {i} raised unexpectedly")
                step_exec.status = "failed"
                step_exec.error = str(e)
                step_exec.result = e.result if isinstance(e, StepError) else None
                step_exec.completed_at = datetime.now(UTC)
                await self.db.commit()
                results.append(None)

                if on_failure == "stop":
                    await self._finish(execution, "failed", f"Step '{step_name}' failed: {e}")
                    await self._notify(execution, runbook, "runbook.failed")
                    return
                failed_steps.append(step_name)
                continue

            step_exec.status = "completed"
            step_exec.result = result_data
            step_exec.completed_at = datetime.now(UTC)
            await self.db.commit()
            results.append(result_data)

        if await self._is_cancelled(execution):
            return
        note = None
        if failed_steps:
            note = f"Completed with {len(failed_steps)} failed step(s): {', '.join(failed_steps)}"
        await self._finish(execution, "completed", note)
        await self._notify(execution, runbook, "runbook.completed")

    # --- steps ---

    async def _execute_step(
        self, execution: RunbookExecution, step: dict, results: list[dict | None]
    ) -> dict:
        action_type = step.get("action_type", "")
        model = STEP_PARAM_MODELS.get(action_type)
        if not model:
            raise StepError(f"Unknown step type: {action_type!r}")
        try:
            params = model.model_validate(step.get("parameters") or {})
        except ValidationError as e:
            raise StepError(f"Invalid parameters: {e}") from None

        if isinstance(params, RemoteActionStepParams):
            return await self._remote_action(execution, params)
        if isinstance(params, WebhookStepParams):
            return await self._webhook(params)
        if isinstance(params, DelayStepParams):
            await self._sleep(params.seconds)
            return {"seconds": params.seconds}
        if isinstance(params, ConditionStepParams):
            return self._condition(params, results)
        raise StepError(f"Unhandled step type: {action_type!r}")

    async def _remote_action(
        self, execution: RunbookExecution, params: RemoteActionStepParams
    ) -> dict:
        result = await self.db.execute(
            select(Agent).where(
                Agent.id == params.agent_id,
                Agent.tenant_id == execution.tenant_id,
                Agent.is_active == True,  # noqa: E712
            )
        )
        if not result.scalar_one_or_none():
            raise StepError("Agent not found or inactive")

        action = RemoteAction(
            tenant_id=execution.tenant_id,
            agent_id=params.agent_id,
            created_by=execution.approved_by or execution.triggered_by,
            action_type=params.action,
            parameters=params.parameters,
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(seconds=params.timeout_seconds),
        )
        self.db.add(action)
        await self.db.commit()

        deadline = self._clock() + params.timeout_seconds
        while action.status not in TERMINAL_ACTION_STATUSES:
            if self._clock() >= deadline:
                if action.status == "pending":
                    # Never picked up: make sure the agent won't run it later
                    action.status = "expired"
                    action.error = "Timed out waiting for the agent"
                    await self.db.commit()
                raise StepError(
                    f"Agent did not finish within {params.timeout_seconds}s "
                    f"(action {action.id} is {action.status})",
                    result={"action_id": str(action.id), "status": action.status},
                )
            await self._sleep(self.poll_interval)
            await self.db.refresh(action)
            if await self._is_cancelled(execution):
                if action.status == "pending":
                    action.status = "expired"
                    action.error = "Runbook execution cancelled"
                    await self.db.commit()
                raise ExecutionCancelled()

        step_result = {
            "action_id": str(action.id),
            "status": action.status,
            "result": action.result,
        }
        if action.status != "completed":
            raise StepError(action.error or f"Remote action {action.status}", result=step_result)
        returncode = (action.result or {}).get("returncode")
        if returncode not in (None, 0):
            raise StepError(f"Command exited with code {returncode}", result=step_result)
        return step_result

    async def _webhook(self, params: WebhookStepParams) -> dict:
        try:
            await validate_outbound_url_async(params.url)
        except UnsafeURLError as e:
            raise StepError(str(e)) from None

        try:
            # Redirects are not followed: their targets would bypass the URL check
            async with httpx.AsyncClient(
                timeout=params.timeout_seconds, follow_redirects=False
            ) as client:
                resp = await client.request(
                    params.method,
                    params.url,
                    headers=params.headers,
                    json=params.body if params.body is not None else None,
                )
        except httpx.HTTPError as e:
            raise StepError(f"Request failed: {e}") from None

        result = {"status_code": resp.status_code, "body": resp.text[:2000]}
        if not 200 <= resp.status_code < 300:
            raise StepError(f"Webhook returned HTTP {resp.status_code}", result=result)
        return result

    @staticmethod
    def _condition(params: ConditionStepParams, results: list[dict | None]) -> dict:
        if params.step >= len(results) or results[params.step] is None:
            raise StepError(f"Step {params.step} has no result to check (it failed or hasn't run)")

        actual: Any = results[params.step]
        for part in params.path.split("."):
            if not isinstance(actual, dict) or part not in actual:
                raise StepError(f"Path {params.path!r} not found in step {params.step}'s result")
            actual = actual[part]

        try:
            passed = _compare(actual, params.operator, params.value)
        except TypeError:
            raise StepError(
                f"Cannot compare {actual!r} {params.operator} {params.value!r}",
                result={"actual": actual},
            ) from None
        if not passed:
            raise StepError(
                f"Condition not met: {params.path} = {actual!r}, "
                f"expected {params.operator} {params.value!r}",
                result={"actual": actual, "passed": False},
            )
        return {"actual": actual, "passed": True}

    # --- helpers ---

    async def _is_cancelled(self, execution: RunbookExecution) -> bool:
        await self.db.refresh(execution)
        return execution.status == "cancelled"

    async def _finish(self, execution: RunbookExecution, status: str, error: str | None) -> None:
        execution.status = status
        execution.error = error
        execution.completed_at = datetime.now(UTC)
        await self.db.commit()

    async def _notify(self, execution: RunbookExecution, runbook: Runbook, event: str) -> None:
        from app.integrations.dispatcher import dispatch_webhook

        try:
            await dispatch_webhook(
                self.db,
                execution.tenant_id,
                event,
                {
                    "execution_id": str(execution.id),
                    "runbook_id": str(runbook.id),
                    "runbook_name": runbook.name,
                    "status": execution.status,
                    "error": execution.error,
                },
            )
            await self.db.commit()
        except Exception:
            # Notification problems must never change the execution's outcome
            logger.exception(f"Failed to dispatch {event} for execution {execution.id}")
            await self.db.rollback()


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    if operator == "contains":
        return expected in actual
    raise TypeError(f"Unknown operator {operator!r}")
