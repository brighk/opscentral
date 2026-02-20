import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.runbooks.models import Runbook, RunbookExecution, RunbookStepExecution
from app.runbooks.schemas import (
    RunbookCreate,
    RunbookExecuteRequest,
    RunbookExecutionResponse,
    RunbookResponse,
    RunbookStepExecutionResponse,
    RunbookUpdate,
)
from app.runbooks.engine import RunbookEngine

router = APIRouter(prefix="/api/v1/runbooks", tags=["runbooks"])


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
        runbook.steps = [s.model_dump() for s in data.steps]
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

    initial_status = "pending_approval" if runbook.requires_approval else "approved"
    execution = RunbookExecution(
        runbook_id=runbook.id,
        tenant_id=user.tenant_id,
        status=initial_status,
        triggered_by=user.id,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    if not runbook.requires_approval:
        engine = RunbookEngine(db)
        await engine.execute_runbook(execution.id)
        await db.refresh(execution)

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

    engine = RunbookEngine(db)
    await engine.execute_runbook(execution.id)
    await db.refresh(execution)
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
    if execution.status not in ("pending_approval", "approved"):
        raise HTTPException(status_code=400, detail="Cannot cancel this execution")

    execution.status = "cancelled"
    execution.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(execution)
    return execution
