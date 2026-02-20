import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.remote_actions.models import PREDEFINED_ACTIONS, RemoteAction
from app.remote_actions.schemas import (
    ActionTypeResponse,
    RemoteActionCreate,
    RemoteActionResponse,
)

router = APIRouter(prefix="/api/v1/remote-actions", tags=["remote-actions"])


@router.get("/types", response_model=list[ActionTypeResponse])
async def list_action_types():
    return [
        ActionTypeResponse(key=key, **{k: v for k, v in action.items() if k != "parameters_schema"})
        for key, action in PREDEFINED_ACTIONS.items()
    ]


@router.post("", response_model=RemoteActionResponse)
async def create_action(
    body: RemoteActionCreate,
    user: User = Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    if body.action_type not in PREDEFINED_ACTIONS:
        raise BadRequestError(f"Unknown action type: {body.action_type}")

    action_def = PREDEFINED_ACTIONS[body.action_type]

    # Check role requirement
    if action_def["min_role"] == "admin" and user.role != "admin":
        raise ForbiddenError("This action requires admin role")

    # Verify agent belongs to tenant
    from app.agents.models import Agent

    result = await db.execute(
        select(Agent).where(
            Agent.id == body.agent_id,
            Agent.tenant_id == user.tenant_id,
            Agent.is_active == True,  # noqa: E712
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Agent not found or inactive")

    action = RemoteAction(
        tenant_id=user.tenant_id,
        agent_id=body.agent_id,
        created_by=user.id,
        action_type=body.action_type,
        parameters=body.parameters,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(action)
    await db.flush()
    return action


@router.get("", response_model=list[RemoteActionResponse])
async def list_actions(
    agent_id: uuid.UUID | None = Query(None),
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(RemoteAction).where(RemoteAction.tenant_id == user.tenant_id)
    if agent_id:
        query = query.where(RemoteAction.agent_id == agent_id)
    if status:
        query = query.where(RemoteAction.status == status)
    query = query.order_by(RemoteAction.created_at.desc()).limit(100)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{action_id}", response_model=RemoteActionResponse)
async def get_action(
    action_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RemoteAction).where(
            RemoteAction.id == action_id,
            RemoteAction.tenant_id == user.tenant_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise NotFoundError("Action not found")
    return action


@router.post("/{action_id}/cancel")
async def cancel_action(
    action_id: uuid.UUID,
    user: User = Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(RemoteAction).where(
            RemoteAction.id == action_id,
            RemoteAction.tenant_id == user.tenant_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise NotFoundError("Action not found")
    if action.status not in ("pending", "dispatched"):
        raise BadRequestError(f"Cannot cancel action in '{action.status}' status")
    action.status = "failed"
    action.error = "Cancelled by user"
    action.completed_at = datetime.now(timezone.utc)
    return {"status": "cancelled"}
