import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent
from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.remote_actions.models import PREDEFINED_ACTIONS
from app.runbooks import dispatch
from app.runbooks.models import Runbook, RunbookExecution, RunbookStepExecution
from app.runbooks.schemas import (
    RunbookCreate,
    RunbookExecuteRequest,
    RunbookExecutionResponse,
    RunbookResponse,
    RunbookStepExecutionResponse,
    RunbookStepSchema,
    RunbookUpdate,
)

router = APIRouter(prefix="/api/v1/runbooks", tags=["runbooks"])


def _admin_only_actions(steps: list[dict]) -> list[str]:
    """Remote actions in these steps that only admins may trigger (e.g. custom_script)."""
    return [
        step["parameters"]["action"]
        for step in steps
        if step.get("action_type") == "remote_action"
        and PREDEFINED_ACTIONS.get(step.get("parameters", {}).get("action", ""), {}).get("min_role")
        == "admin"
    ]


async def _validate_steps(steps: list[RunbookStepSchema], user: User, db: AsyncSession) -> None:
    step_dicts = [s.model_dump() for s in steps]
    admin_only = _admin_only_actions(step_dicts)
    if admin_only and user.role != "admin":
        actions = ", ".join(sorted(set(admin_only)))
        raise HTTPException(
            status_code=403, detail=f"Only admins can add these remote actions: {actions}"
        )

    agent_ids = {
        uuid.UUID(s.parameters["agent_id"]) for s in steps if s.action_type == "remote_action"
    }
    if agent_ids:
        result = await db.execute(
            select(Agent.id).where(Agent.id.in_(agent_ids), Agent.tenant_id == user.tenant_id)
        )
        missing = agent_ids - set(result.scalars().all())
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent(s): {', '.join(str(a) for a in sorted(missing, key=str))}",
            )


async def _queue(execution: RunbookExecution, db: AsyncSession) -> None:
    try:
        await dispatch.dispatch_execution(execution.id)
    except dispatch.QueueUnavailableError:
        execution.status = "failed"
        execution.error = "Could not queue the execution: background worker queue is unavailable"
        execution.completed_at = datetime.now(UTC)
        await db.commit()
    await db.refresh(execution)


@router.get("", response_model=list[RunbookResponse])
async def list_runbooks(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook)
        .where(Runbook.tenant_id == user.tenant_id)
        .order_by(Runbook.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=RunbookResponse)
async def create_runbook(
    data: RunbookCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    await _validate_steps(data.steps, user, db)
    runbook = Runbook(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        steps=[s.model_dump() for s in data.steps],
        trigger_type=data.trigger_type,
        requires_approval=data.requires_approval,
        created_by=user.id,
    )
    db.add(runbook)
    await db.commit()
    await db.refresh(runbook)
    return runbook


@router.get("/{runbook_id}", response_model=RunbookResponse)
async def get_runbook(
    runbook_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook).where(
            Runbook.id == runbook_id,
            Runbook.tenant_id == user.tenant_id,
        )
    )
    runbook = result.scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    return runbook


@router.put("/{runbook_id}", response_model=RunbookResponse)
async def update_runbook(
    runbook_id: uuid.UUID,
    data: RunbookUpdate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook).where(
            Runbook.id == runbook_id,
            Runbook.tenant_id == user.tenant_id,
        )
    )
    runbook = result.scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")

    if data.name is not None:
        runbook.name = data.name
    if data.description is not None:
        runbook.description = data.description
    if data.steps is not None:
        await _validate_steps(data.steps, user, db)
        runbook.steps = [s.model_dump() for s in data.steps]
    elif _admin_only_actions(runbook.steps) and user.role != "admin":
        raise HTTPException(
            status_code=403, detail="Only admins can edit runbooks with admin-only remote actions"
        )
    if data.trigger_type is not None:
        runbook.trigger_type = data.trigger_type
    if data.requires_approval is not None:
        runbook.requires_approval = data.requires_approval
    if data.is_enabled is not None:
        runbook.is_enabled = data.is_enabled

    await db.commit()
    await db.refresh(runbook)
    return runbook


@router.delete("/{runbook_id}")
async def delete_runbook(
    runbook_id: uuid.UUID,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook).where(
            Runbook.id == runbook_id,
            Runbook.tenant_id == user.tenant_id,
        )
    )
    runbook = result.scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")

    await db.delete(runbook)
    await db.commit()
    return {"detail": "Runbook deleted"}


@router.post("/{runbook_id}/execute", response_model=RunbookExecutionResponse)
async def execute_runbook(
    runbook_id: uuid.UUID,
    data: RunbookExecuteRequest = RunbookExecuteRequest(),
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Runbook).where(
            Runbook.id == runbook_id,
            Runbook.tenant_id == user.tenant_id,
        )
    )
    runbook = result.scalar_one_or_none()
    if not runbook:
        raise HTTPException(status_code=404, detail="Runbook not found")
    if not runbook.is_enabled:
        raise HTTPException(status_code=400, detail="Runbook is disabled")

    # Operators may run runbooks containing admin-only actions, but an admin must approve
    needs_approval = runbook.requires_approval or (
        user.role != "admin" and bool(_admin_only_actions(runbook.steps))
    )
    execution = RunbookExecution(
        runbook_id=runbook.id,
        tenant_id=user.tenant_id,
        status="pending_approval" if needs_approval else "approved",
        triggered_by=user.id,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    if not needs_approval:
        await _queue(execution, db)
    return execution


@router.get("/{runbook_id}/executions", response_model=list[RunbookExecutionResponse])
async def list_executions(
    runbook_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RunbookExecution)
        .where(
            RunbookExecution.runbook_id == runbook_id,
            RunbookExecution.tenant_id == user.tenant_id,
        )
        .order_by(RunbookExecution.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.get("/executions/{execution_id}/steps", response_model=list[RunbookStepExecutionResponse])
async def list_execution_steps(
    execution_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(RunbookExecution).where(
            RunbookExecution.id == execution_id,
            RunbookExecution.tenant_id == user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Execution not found")

    result = await db.execute(
        select(RunbookStepExecution)
        .where(RunbookStepExecution.execution_id == execution_id)
        .order_by(RunbookStepExecution.step_index)
    )
    return result.scalars().all()


@router.post("/executions/{execution_id}/approve", response_model=RunbookExecutionResponse)
async def approve_execution(
    execution_id: uuid.UUID,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RunbookExecution).where(
            RunbookExecution.id == execution_id,
            RunbookExecution.tenant_id == user.tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    if execution.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Execution is not pending approval")

    execution.status = "approved"
    execution.approved_by = user.id
    await db.commit()

    await _queue(execution, db)
    return execution


@router.post("/executions/{execution_id}/cancel", response_model=RunbookExecutionResponse)
async def cancel_execution(
    execution_id: uuid.UUID,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RunbookExecution).where(
            RunbookExecution.id == execution_id,
            RunbookExecution.tenant_id == user.tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    # A running execution stops before its next step (or while waiting on an agent)
    if execution.status not in ("pending_approval", "approved", "running"):
        raise HTTPException(status_code=400, detail="Cannot cancel this execution")

    execution.status = "cancelled"
    execution.completed_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(execution)
    return execution
