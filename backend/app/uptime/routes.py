"""Uptime monitoring routes — uptime stats, SSL cert info, and public status page."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import Tenant, User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.healthchecks.models import HealthCheck, HealthCheckLog
from app.uptime.ssl_checker import check_ssl_cert

router = APIRouter(prefix="/api/v1/uptime", tags=["uptime"])


@router.get("/stats")
async def get_uptime_stats(
    check_id: uuid.UUID | None = None,
    period: str = Query("24h", pattern="^(1h|6h|24h|7d|30d)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get uptime percentage and response time stats for health checks."""
    period_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
    hours = period_map[period]
    since = datetime.now(UTC) - timedelta(hours=hours)

    # Get checks for this tenant
    check_query = select(HealthCheck).where(
        HealthCheck.tenant_id == user.tenant_id,
        HealthCheck.is_enabled == True,  # noqa: E712
    )
    if check_id:
        check_query = check_query.where(HealthCheck.id == check_id)

    checks_result = await db.execute(check_query)
    checks = checks_result.scalars().all()

    stats = []
    for check in checks:
        # Get logs for the period
        log_result = await db.execute(
            select(
                func.count(HealthCheckLog.id).label("total"),
                func.sum(case((HealthCheckLog.status == "up", 1), else_=0)).label("up_count"),
                func.avg(HealthCheckLog.response_time_ms).label("avg_response_time"),
                func.min(HealthCheckLog.response_time_ms).label("min_response_time"),
                func.max(HealthCheckLog.response_time_ms).label("max_response_time"),
            ).where(
                HealthCheckLog.check_id == check.id,
                HealthCheckLog.checked_at >= since,
            )
        )
        row = log_result.one()

        total = row.total or 0
        up_count = int(row.up_count or 0)
        uptime_pct = round((up_count / total) * 100, 2) if total > 0 else None

        # Get SSL cert info for HTTPS checks
        ssl_info = None
        if check.check_type == "http" and check.target.startswith("https://"):
            ssl_info = check_ssl_cert(check.target, timeout=check.timeout_seconds)

        stats.append(
            {
                "check_id": str(check.id),
                "name": check.name,
                "check_type": check.check_type,
                "target": check.target,
                "status": check.status,
                "uptime_percent": uptime_pct,
                "total_checks": total,
                "successful_checks": up_count,
                "avg_response_time_ms": round(float(row.avg_response_time), 2)
                if row.avg_response_time
                else None,
                "min_response_time_ms": round(float(row.min_response_time), 2)
                if row.min_response_time
                else None,
                "max_response_time_ms": round(float(row.max_response_time), 2)
                if row.max_response_time
                else None,
                "last_checked_at": check.last_checked_at.isoformat()
                if check.last_checked_at
                else None,
                "ssl_certificate": ssl_info,
            }
        )

    return stats


@router.get("/response-times/{check_id}")
async def get_response_times(
    check_id: uuid.UUID,
    period: str = Query("24h", pattern="^(1h|6h|24h|7d|30d)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get response time history for charting."""
    # Verify check belongs to tenant
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.id == check_id,
            HealthCheck.tenant_id == user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Health check not found")

    period_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
    since = datetime.now(UTC) - timedelta(hours=period_map[period])

    result = await db.execute(
        select(
            HealthCheckLog.checked_at,
            HealthCheckLog.response_time_ms,
            HealthCheckLog.status,
            HealthCheckLog.status_code,
        )
        .where(
            HealthCheckLog.check_id == check_id,
            HealthCheckLog.checked_at >= since,
        )
        .order_by(HealthCheckLog.checked_at.asc())
    )
    logs = result.all()

    return [
        {
            "timestamp": log.checked_at.isoformat(),
            "response_time_ms": log.response_time_ms,
            "status": log.status,
            "status_code": log.status_code,
        }
        for log in logs
    ]


@router.get("/ssl/{check_id}")
async def get_ssl_info(
    check_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get SSL certificate details for an HTTPS health check."""
    result = await db.execute(
        select(HealthCheck).where(
            HealthCheck.id == check_id,
            HealthCheck.tenant_id == user.tenant_id,
        )
    )
    check = result.scalar_one_or_none()
    if not check:
        raise NotFoundError("Health check not found")

    if check.check_type != "http" or not check.target.startswith("https://"):
        return {"error": "Not an HTTPS check", "ssl_certificate": None}

    ssl_info = check_ssl_cert(check.target, timeout=check.timeout_seconds)
    return {"check_id": str(check.id), "target": check.target, "ssl_certificate": ssl_info}


# --- Public Status Page (no authentication required) ---

public_router = APIRouter(prefix="/api/v1/status", tags=["status-page"])


@public_router.get("/{tenant_slug}")
async def public_status_page(
    tenant_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Public status page showing health check statuses for a tenant.

    Uses the tenant name (lowercased, hyphenated) as the slug.
    """
    # Find tenant by slug (name lowercased with spaces replaced by hyphens)
    result = await db.execute(select(Tenant))
    tenants = result.scalars().all()

    tenant = None
    for t in tenants:
        slug = t.name.lower().replace(" ", "-")
        if slug == tenant_slug:
            tenant = t
            break

    if not tenant:
        raise NotFoundError("Status page not found")

    # Get enabled health checks for this tenant
    checks_result = await db.execute(
        select(HealthCheck)
        .where(
            HealthCheck.tenant_id == tenant.id,
            HealthCheck.is_enabled == True,  # noqa: E712
        )
        .order_by(HealthCheck.name)
    )
    checks = checks_result.scalars().all()

    since_24h = datetime.now(UTC) - timedelta(hours=24)

    services = []
    for check in checks:
        # Calculate 24h uptime
        log_result = await db.execute(
            select(
                func.count(HealthCheckLog.id).label("total"),
                func.sum(case((HealthCheckLog.status == "up", 1), else_=0)).label("up_count"),
            ).where(
                HealthCheckLog.check_id == check.id,
                HealthCheckLog.checked_at >= since_24h,
            )
        )
        row = log_result.one()
        total = row.total or 0
        up_count = int(row.up_count or 0)
        uptime_pct = round((up_count / total) * 100, 2) if total > 0 else None

        services.append(
            {
                "name": check.name,
                "status": check.status,
                "uptime_24h": uptime_pct,
                "last_checked_at": check.last_checked_at.isoformat()
                if check.last_checked_at
                else None,
                "response_time_ms": check.last_response_time_ms,
            }
        )

    # Overall status
    all_up = all(s["status"] == "up" for s in services) if services else True
    any_down = any(s["status"] == "down" for s in services)
    overall = "operational" if all_up else ("major_outage" if any_down else "degraded")

    return {
        "organization": tenant.name,
        "overall_status": overall,
        "services": services,
        "updated_at": datetime.now(UTC).isoformat(),
    }
