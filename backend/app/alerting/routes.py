import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerting.models import Alert, AlertRule
from app.alerting.schemas import (
    AlertResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)
from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/alerting", tags=["alerting"])


# --- Alert Rules CRUD ---

@router.get("/rules", response_model=list[AlertRuleResponse])
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlertRule)
        .where(AlertRule.tenant_id == user.tenant_id)
        .order_by(AlertRule.created_at.desc())
    )
    return result.scalars().all()


@router.post("/rules", response_model=AlertRuleResponse)
async def create_rule(
    body: AlertRuleCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rule = AlertRule(
        tenant_id=user.tenant_id,
        name=body.name,
        description=body.description,
        metric_name=body.metric_name,
        condition=body.condition,
        threshold=body.threshold,
        duration_seconds=body.duration_seconds,
        agent_id=body.agent_id,
        severity=body.severity,
        notify_email=body.notify_email,
    )
    db.add(rule)
    await db.flush()
    return rule


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    body: AlertRuleUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == user.tenant_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("Alert rule not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rule, key, value)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AlertRule).where(AlertRule.id == rule_id, AlertRule.tenant_id == user.tenant_id)
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("Alert rule not found")
    await db.delete(rule)
    return {"status": "deleted"}


# --- Alerts ---

@router.get("/alerts", response_model=PaginatedResponse[AlertResponse])
async def list_alerts(
    status: str | None = Query(None),
    pagination: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Alert).where(Alert.tenant_id == user.tenant_id)
    if status:
        base = base.where(Alert.status == status)

    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(Alert.fired_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.tenant_id == user.tenant_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise NotFoundError("Alert not found")
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.now(timezone.utc)
    alert.acknowledged_by = user.id
    return {"status": "acknowledged"}


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Alert).where(Alert.id == alert_id, Alert.tenant_id == user.tenant_id)
    )
    alert = result.scalar_one_or_none()
    if not alert:
        raise NotFoundError("Alert not found")
    alert.status = "resolved"
    alert.resolved_at = datetime.now(timezone.utc)
    return {"status": "resolved"}
