import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.runbooks.models import Runbook, RunbookExecution, RunbookStepExecution


class RunbookEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute_runbook(self, execution_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(RunbookExecution).where(RunbookExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if not execution:
            return

        result = await self.db.execute(select(Runbook).where(Runbook.id == execution.runbook_id))
        runbook = result.scalar_one_or_none()
        if not runbook:
            execution.status = "failed"
            execution.error = "Runbook not found"
            await self.db.commit()
            return

        execution.status = "running"
        execution.started_at = datetime.now(UTC)
        await self.db.commit()

        steps = runbook.steps if isinstance(runbook.steps, list) else []

        for i, step in enumerate(steps):
            step_name = step.get("name", f"Step {i + 1}")
            on_failure = step.get("on_failure", "stop")

            step_exec = RunbookStepExecution(
                execution_id=execution_id,
                step_index=i,
                step_name=step_name,
                status="running",
                started_at=datetime.now(UTC),
            )
            self.db.add(step_exec)
            await self.db.commit()

            try:
                result_data = await self._execute_step(step)
                step_exec.status = "completed"
                step_exec.result = result_data
                step_exec.completed_at = datetime.now(UTC)
                await self.db.commit()
            except Exception as e:
                step_exec.status = "failed"
                step_exec.error = str(e)
                step_exec.completed_at = datetime.now(UTC)
                await self.db.commit()

                if on_failure == "stop":
                    execution.status = "failed"
                    execution.error = f"Step '{step_name}' failed: {e}"
                    execution.completed_at = datetime.now(UTC)
                    await self.db.commit()
                    return
                elif on_failure == "skip":
                    continue

        execution.status = "completed"
        execution.completed_at = datetime.now(UTC)
        await self.db.commit()

    async def _execute_step(self, step: dict) -> dict:
        action_type = step.get("action_type", "")
        parameters = step.get("parameters", {})

        if action_type == "remote_action":
            return {"action": "remote_action", "status": "dispatched", **parameters}
        elif action_type == "webhook":
            return {"action": "webhook", "status": "sent", **parameters}
        elif action_type == "delay":
            seconds = parameters.get("seconds", 0)
            return {"action": "delay", "seconds": seconds}
        elif action_type == "condition":
            return {"action": "condition", "evaluated": True}
        else:
            return {"action": action_type, "status": "executed"}
