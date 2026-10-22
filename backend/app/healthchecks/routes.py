import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.healthchecks.models import HealthCheck, HealthCheckLog
from app.healthchecks.schemas import (
    HealthCheckCreate,
    HealthCheckLogResponse,
    HealthCheckResponse,
    HealthCheckUpdate,
)

router = APIRouter(prefix="/api/v1/healthchecks", tags=["health-checks"])


@router.get("", response_model=list[HealthCheckResponse])
async def list_health_checks(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheck)
        .where(HealthCheck.tenant_id == user.tenant_id)
        .order_by(HealthCheck.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=HealthCheckResponse)
async def create_health_check(
    body: HealthCheckCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    check = HealthCheck(
        tenant_id=user.tenant_id,
        name=body.name,
        check_type=body.check_type,
        target=body.target,
        interval_seconds=body.interval_seconds,
        timeout_seconds=body.timeout_seconds,
        is_enabled=body.is_enabled,
        expected_status=body.expected_status,
        expected_body=body.expected_body,
        http_method=body.http_method,
        http_headers=body.http_headers,
        alert_after_failures=body.alert_after_failures,
        notify_channels=body.notify_channels,
    )
    db.add(check)
    await db.flush()
    return check


@router.get("/{check_id}", response_model=HealthCheckResponse)
async def get_health_check(
    check_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.id == check_id,
            HealthCheck.tenant_id == user.tenant_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise NotFoundError("Health check not found")
    return check


@router.put("/{check_id}", response_model=HealthCheckResponse)
async def update_health_check(
    check_id: uuid.UUID,
    body: HealthCheckUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.id == check_id,
            HealthCheck.tenant_id == user.tenant_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise NotFoundError("Health check not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(check, field, value)
    return check


@router.delete("/{check_id}")
async def delete_health_check(
    check_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.id == check_id,
            HealthCheck.tenant_id == user.tenant_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise NotFoundError("Health check not found")
    await db.delete(check)
    return {"status": "deleted"}


@router.get("/{check_id}/logs", response_model=list[HealthCheckLogResponse])
async def get_health_check_logs(
    check_id: uuid.UUID,
    hours: int = Query(24, ge=1, le=168),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    result = await db.execute(
        select(HealthCheckLog)
        .where(
            HealthCheckLog.check_id == check_id,
            HealthCheckLog.tenant_id == user.tenant_id,
            HealthCheckLog.checked_at >= cutoff,
        )
        .order_by(HealthCheckLog.checked_at.desc())
        .limit(500)
    )
    return result.scalars().all()
