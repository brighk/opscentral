import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.models import Agent
from app.agents.schemas import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentResponse,
    HeartbeatRequest,
    InventoryPayload,
    MetricsPayload,
    ProcessesPayload,
)
from app.agents.status_models import AgentStatusLog
from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_agent_tenant_id, get_current_user
from app.exceptions import NotFoundError
from app.pagination import PaginatedResponse, PaginationParams

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])
gateway = APIRouter(prefix="/api/v1/gateway", tags=["agent-gateway"])


# --- User-facing agent management ---


@router.get("", response_model=PaginatedResponse[AgentResponse])
async def list_agents(
    pagination: PaginationParams = Depends(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Agent).where(Agent.tenant_id == user.tenant_id)
    total_result = await db.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(Agent.created_at.desc()).offset(pagination.offset).limit(pagination.page_size)
    )
    items = result.scalars().all()
    return PaginatedResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=(total + pagination.page_size - 1) // pagination.page_size,
    )


@router.post("/register", response_model=AgentRegisterResponse)
async def register_agent(
    body: AgentRegisterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    agent = Agent(
        tenant_id=user.tenant_id,
        hostname=body.hostname,
        display_name=body.display_name or body.hostname,
        os_type=body.os_type,
        os_version=body.os_version,
        agent_version=body.agent_version,
    )
    db.add(agent)
    await db.flush()
    return AgentRegisterResponse(agent_id=agent.id, api_key=agent.api_key)


@router.delete("/{agent_id}")
async def deactivate_agent(
    agent_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == user.tenant_id)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise NotFoundError("Agent not found")
    agent.is_active = False
    return {"status": "deactivated"}


@router.get("/{agent_id}/status-history")
async def get_agent_status_history(
    agent_id: uuid.UUID,
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get status transition history for an agent."""
    # Verify agent belongs to tenant
    result = await db.execute(
        select(Agent).where(Agent.id == agent_id, Agent.tenant_id == user.tenant_id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Agent not found")

    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(
        select(AgentStatusLog)
        .where(
            AgentStatusLog.agent_id == agent_id,
            AgentStatusLog.recorded_at >= cutoff,
        )
        .order_by(AgentStatusLog.recorded_at.desc())
        .limit(500)
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "status": log.status,
            "message": log.message,
            "recorded_at": log.recorded_at.isoformat(),
        }
        for log in logs
    ]


# --- Agent gateway (API-key auth) ---


@gateway.post("/heartbeat")
async def heartbeat(
    body: HeartbeatRequest,
    agent_info: tuple[uuid.UUID, uuid.UUID] = Depends(get_agent_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    agent_id, tenant_id = agent_info
    now = datetime.now(UTC)

    # Check if agent was previously offline (no heartbeat for 3+ min)
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent and agent.last_seen:
        was_offline = (now - agent.last_seen) > timedelta(minutes=3)
        if was_offline:
            db.add(
                AgentStatusLog(
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    status="online",
                    message=(
                        "Agent came back online after being offline since "
                        f"{agent.last_seen.isoformat()}"
                    ),
                    recorded_at=now,
                )
            )
    elif agent and agent.last_seen is None:
        # First heartbeat ever — record as initial online
        db.add(
            AgentStatusLog(
                tenant_id=tenant_id,
                agent_id=agent_id,
                status="online",
                message="Agent connected for the first time",
                recorded_at=now,
            )
        )

    await db.execute(
        update(Agent)
        .where(Agent.id == agent_id)
        .values(
            last_seen=now,
            agent_version=body.agent_version,
            ip_address=body.ip_address,
        )
    )
    return {"status": "ok"}


@gateway.post("/metrics")
async def ingest_metrics(
    body: MetricsPayload,
    agent_info: tuple[uuid.UUID, uuid.UUID] = Depends(get_agent_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    from app.monitoring.models import Metric

    agent_id, tenant_id = agent_info
    now = datetime.now(UTC)

    for m in body.metrics:
        metric = Metric(
            tenant_id=tenant_id,
            agent_id=agent_id,
            metric_name=m.get("name", "unknown"),
            metric_value=float(m.get("value", 0)),
            unit=m.get("unit", ""),
            tags=m.get("tags"),
            recorded_at=now,
        )
        db.add(metric)

    # Update last_seen
    await db.execute(update(Agent).where(Agent.id == agent_id).values(last_seen=now))

    # Publish to Redis for real-time dashboard
    try:
        import json

        import redis.asyncio as aioredis

        from app.config import settings

        r = aioredis.from_url(settings.REDIS_URL)
        await r.publish(
            f"dashboard:{tenant_id}",
            json.dumps({"type": "metrics", "agent_id": str(agent_id), "count": len(body.metrics)}),
        )
        await r.aclose()
    except Exception:
        pass  # Non-critical

    return {"status": "ok", "ingested": len(body.metrics)}


@gateway.post("/inventory")
async def submit_inventory(
    body: InventoryPayload,
    agent_info: tuple[uuid.UUID, uuid.UUID] = Depends(get_agent_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    from app.assets.models import Asset, SoftwareInventory

    agent_id, tenant_id = agent_info
    info = body.system_info

    # Upsert asset
    result = await db.execute(select(Asset).where(Asset.agent_id == agent_id))
    asset = result.scalar_one_or_none()

    if not asset:
        # Enforce asset limit before creating new assets
        from app.billing.service import enforce_asset_limit

        await enforce_asset_limit(tenant_id, db)

    if asset:
        asset.hostname = info.get("hostname", asset.hostname)
        asset.os_type = info.get("os_type", asset.os_type)
        asset.os_version = info.get("os_version", asset.os_version)
        asset.cpu_model = info.get("cpu_model")
        asset.cpu_cores = info.get("cpu_cores")
        asset.ram_total_gb = info.get("ram_total_gb")
        asset.disk_total_gb = info.get("disk_total_gb")
        asset.ip_addresses = info.get("ip_addresses")
        asset.mac_addresses = info.get("mac_addresses")
        asset.system_info = info
    else:
        asset = Asset(
            tenant_id=tenant_id,
            agent_id=agent_id,
            hostname=info.get("hostname", "unknown"),
            os_type=info.get("os_type"),
            os_version=info.get("os_version"),
            cpu_model=info.get("cpu_model"),
            cpu_cores=info.get("cpu_cores"),
            ram_total_gb=info.get("ram_total_gb"),
            disk_total_gb=info.get("disk_total_gb"),
            ip_addresses=info.get("ip_addresses"),
            mac_addresses=info.get("mac_addresses"),
            system_info=info,
        )
        db.add(asset)
    await db.flush()

    # Update software inventory
    if body.software:
        # Clear old entries
        from sqlalchemy import delete

        await db.execute(delete(SoftwareInventory).where(SoftwareInventory.asset_id == asset.id))
        for sw in body.software:
            db.add(
                SoftwareInventory(
                    asset_id=asset.id,
                    name=sw.get("name", "unknown"),
                    version=sw.get("version"),
                    publisher=sw.get("publisher"),
                )
            )

    return {"status": "ok", "asset_id": str(asset.id)}


@gateway.get("/actions/poll")
async def poll_actions(
    agent_info: tuple[uuid.UUID, uuid.UUID] = Depends(get_agent_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Agent polls for pending actions."""
    from app.remote_actions.models import RemoteAction

    agent_id, _tenant_id = agent_info
    now = datetime.now(UTC)

    result = await db.execute(
        select(RemoteAction)
        .where(
            RemoteAction.agent_id == agent_id,
            RemoteAction.status == "pending",
            RemoteAction.expires_at > now,
        )
        .order_by(RemoteAction.created_at.asc())
    )
    actions = result.scalars().all()

    # Mark as dispatched
    for action in actions:
        action.status = "dispatched"

    return [
        {
            "id": str(a.id),
            "action_type": a.action_type,
            "parameters": a.parameters,
        }
        for a in actions
    ]


@gateway.post("/actions/{action_id}/result")
async def report_action_result(
    action_id: uuid.UUID,
    body: dict,
    agent_info: tuple[uuid.UUID, uuid.UUID] = Depends(get_agent_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    """Agent reports action result."""
    from app.remote_actions.models import RemoteAction

    agent_id, _tenant_id = agent_info

    result = await db.execute(
        select(RemoteAction).where(
            RemoteAction.id == action_id,
            RemoteAction.agent_id == agent_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise NotFoundError("Action not found")

    action.status = body.get("status", "completed")
    action.result = body.get("result")
    action.error = body.get("error")
    action.completed_at = datetime.now(UTC)

    return {"status": "ok"}


@gateway.post("/processes")
async def submit_processes(
    body: ProcessesPayload,
    agent_info: tuple[uuid.UUID, uuid.UUID] = Depends(get_agent_tenant_id),
    db: AsyncSession = Depends(get_db),
):
    from app.monitoring.process_models import ProcessSnapshot

    agent_id, tenant_id = agent_info
    now = datetime.now(UTC)

    # Delete old snapshots for this agent (keep only latest)
    from sqlalchemy import delete

    await db.execute(delete(ProcessSnapshot).where(ProcessSnapshot.agent_id == agent_id))

    for proc in body.processes:
        snapshot = ProcessSnapshot(
            tenant_id=tenant_id,
            agent_id=agent_id,
            pid=proc.get("pid", 0),
            name=proc.get("name", "unknown"),
            cpu_percent=proc.get("cpu_percent", 0),
            memory_percent=proc.get("memory_percent", 0),
            memory_mb=proc.get("memory_mb", 0),
            status=proc.get("status", "unknown"),
            username=proc.get("username"),
            num_threads=proc.get("num_threads", 0),
            command=proc.get("command", "")[:500],
            recorded_at=now,
        )
        db.add(snapshot)

    return {"status": "ok", "ingested": len(body.processes)}
