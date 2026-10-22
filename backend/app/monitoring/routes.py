import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent
from app.alerting.models import Alert
from app.assets.models import Asset
from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.monitoring.models import Metric
from app.monitoring.process_models import ProcessSnapshot
from app.monitoring.schemas import StatusOverview

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


@router.get("/metrics")
async def query_metrics(
    agent_id: uuid.UUID | None = Query(None),
    metric_name: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    bucket_seconds: int = Query(300),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not start:
        start = datetime.now(UTC) - timedelta(hours=1)
    if not end:
        end = datetime.now(UTC)

    # Use date_trunc on PostgreSQL; on SQLite, just use recorded_at directly
    dialect = db.bind.dialect.name if db.bind else "postgresql"
    if dialect == "sqlite":
        bucket_expr = Metric.recorded_at
    else:
        bucket_expr = func.date_trunc("minute", Metric.recorded_at)

    query = (
        select(
            bucket_expr.label("time_bucket"),
            Metric.metric_name,
            Metric.agent_id,
            func.avg(Metric.metric_value).label("avg_value"),
            func.min(Metric.metric_value).label("min_value"),
            func.max(Metric.metric_value).label("max_value"),
        )
        .where(
            Metric.tenant_id == user.tenant_id,
            Metric.recorded_at >= start,
            Metric.recorded_at <= end,
        )
        .group_by(bucket_expr, Metric.metric_name, Metric.agent_id)
        .order_by(bucket_expr)
    )

    if agent_id:
        query = query.where(Metric.agent_id == agent_id)
    if metric_name:
        query = query.where(Metric.metric_name == metric_name)

    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "time_bucket": row.time_bucket.isoformat(),
            "metric_name": row.metric_name,
            "agent_id": str(row.agent_id),
            "avg_value": round(row.avg_value, 2),
            "min_value": round(row.min_value, 2),
            "max_value": round(row.max_value, 2),
        }
        for row in rows
    ]


@router.get("/status", response_model=StatusOverview)
async def status_overview(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = user.tenant_id
    cutoff = datetime.now(UTC) - timedelta(minutes=3)
    hour_ago = datetime.now(UTC) - timedelta(hours=1)

    total_agents = (
        await db.scalar(
            select(func.count())
            .select_from(Agent)
            .where(
                Agent.tenant_id == tenant_id,
                Agent.is_active == True,  # noqa: E712
            )
        )
        or 0
    )

    online_agents = (
        await db.scalar(
            select(func.count())
            .select_from(Agent)
            .where(
                Agent.tenant_id == tenant_id,
                Agent.is_active == True,  # noqa: E712
                Agent.last_seen >= cutoff,
            )
        )
        or 0
    )

    total_assets = (
        await db.scalar(select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id))
        or 0
    )

    active_alerts = (
        await db.scalar(
            select(func.count())
            .select_from(Alert)
            .where(Alert.tenant_id == tenant_id, Alert.status == "firing")
        )
        or 0
    )

    metrics_count = (
        await db.scalar(
            select(func.count())
            .select_from(Metric)
            .where(Metric.tenant_id == tenant_id, Metric.recorded_at >= hour_ago)
        )
        or 0
    )

    return StatusOverview(
        total_agents=total_agents,
        online_agents=online_agents,
        offline_agents=total_agents - online_agents,
        total_assets=total_assets,
        active_alerts=active_alerts,
        metrics_last_hour=metrics_count,
    )


@router.get("/processes")
async def list_processes(
    agent_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get latest process snapshots, optionally filtered by agent."""
    query = (
        select(ProcessSnapshot)
        .where(ProcessSnapshot.tenant_id == user.tenant_id)
        .order_by(ProcessSnapshot.cpu_percent.desc())
    )
    if agent_id:
        query = query.where(ProcessSnapshot.agent_id == agent_id)

    result = await db.execute(query)
    snapshots = result.scalars().all()

    return [
        {
            "pid": s.pid,
            "name": s.name,
            "cpu_percent": s.cpu_percent,
            "memory_percent": s.memory_percent,
            "memory_mb": s.memory_mb,
            "status": s.status,
            "username": s.username,
            "num_threads": s.num_threads,
            "command": s.command,
            "agent_id": str(s.agent_id),
            "recorded_at": s.recorded_at.isoformat(),
        }
        for s in snapshots
    ]
