import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.incidents.models import Incident, IncidentUpdate as IncidentUpdateModel


async def create_incident_from_alert(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    alert_id: uuid.UUID,
    title: str,
    severity: str,
    created_by: uuid.UUID,
) -> Incident:
    incident = Incident(
        tenant_id=tenant_id,
        title=title,
        severity=severity,
        source="alert",
        alert_id=alert_id,
        created_by=created_by,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident


async def auto_resolve_incident(
    db: AsyncSession,
    incident_id: uuid.UUID,
    resolved_by: uuid.UUID,
) -> Incident | None:
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident or incident.status in ("resolved", "closed"):
        return incident

    incident.status = "resolved"
    incident.resolved_at = datetime.now(timezone.utc)

    update = IncidentUpdateModel(
        incident_id=incident.id,
        message="Incident auto-resolved",
        update_type="resolution",
        created_by=resolved_by,
        new_status="resolved",
    )
    db.add(update)
    await db.commit()
    await db.refresh(incident)
    return incident


async def calculate_mttr(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> float | None:
    result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", Incident.resolved_at) -
                func.extract("epoch", Incident.created_at)
            )
        ).where(
            Incident.tenant_id == tenant_id,
            Incident.resolved_at.isnot(None),
        )
    )
    avg_seconds = result.scalar()
    if avg_seconds is None:
        return None
    return round(avg_seconds / 3600, 2)
