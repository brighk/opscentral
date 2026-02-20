import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.incidents.models import (
    Incident,
    IncidentUpdate as IncidentUpdateModel,
    IncidentTag,
    Postmortem,
)
from app.incidents.schemas import (
    IncidentCreate,
    IncidentUpdate,
    IncidentResponse,
    IncidentUpdateCreate,
    IncidentUpdateResponse,
    PostmortemCreate,
    PostmortemResponse,
    IncidentStatsResponse,
)
from app.incidents.service import calculate_mttr

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    status: str | None = Query(None),
    severity: str | None = Query(None),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Incident).where(Incident.tenant_id == user.tenant_id)
    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
    query = query.order_by(Incident.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=IncidentResponse)
async def create_incident(
    data: IncidentCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    incident = Incident(
        tenant_id=user.tenant_id,
        title=data.title,
        description=data.description,
        severity=data.severity,
        source=data.source,
        alert_id=data.alert_id,
        assigned_to=data.assigned_to,
        commander_id=data.commander_id,
        created_by=user.id,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident


@router.get("/stats", response_model=IncidentStatsResponse)
async def get_stats(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(func.count()).select_from(Incident).where(
        Incident.tenant_id == user.tenant_id
    )
    total = (await db.execute(base)).scalar() or 0
    open_count = (await db.execute(base.where(Incident.status == "open"))).scalar() or 0
    investigating = (await db.execute(base.where(Incident.status == "investigating"))).scalar() or 0
    resolved = (await db.execute(base.where(Incident.status == "resolved"))).scalar() or 0
    closed = (await db.execute(base.where(Incident.status == "closed"))).scalar() or 0

    mttr = await calculate_mttr(db, user.tenant_id)

    return IncidentStatsResponse(
        total=total,
        open=open_count,
        investigating=investigating,
        resolved=resolved,
        closed=closed,
        mttr_hours=mttr,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.tenant_id == user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.put("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: uuid.UUID,
    data: IncidentUpdate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.tenant_id == user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if data.title is not None:
        incident.title = data.title
    if data.description is not None:
        incident.description = data.description
    if data.severity is not None:
        incident.severity = data.severity
    if data.status is not None:
        incident.status = data.status
    if data.assigned_to is not None:
        incident.assigned_to = data.assigned_to
    if data.commander_id is not None:
        incident.commander_id = data.commander_id

    await db.commit()
    await db.refresh(incident)
    return incident


@router.delete("/{incident_id}")
async def delete_incident(
    incident_id: uuid.UUID,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.tenant_id == user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    await db.delete(incident)
    await db.commit()
    return {"detail": "Incident deleted"}


@router.post("/{incident_id}/updates", response_model=IncidentUpdateResponse)
async def add_update(
    incident_id: uuid.UUID,
    data: IncidentUpdateCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.tenant_id == user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    update = IncidentUpdateModel(
        incident_id=incident.id,
        message=data.message,
        update_type=data.update_type,
        created_by=user.id,
        new_status=data.new_status,
    )
    db.add(update)

    if data.new_status:
        incident.status = data.new_status
        if data.new_status == "resolved":
            incident.resolved_at = datetime.now(timezone.utc)
        elif data.new_status == "closed":
            incident.closed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(update)
    return update


@router.get("/{incident_id}/updates", response_model=list[IncidentUpdateResponse])
async def list_updates(
    incident_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.tenant_id == user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Incident not found")

    result = await db.execute(
        select(IncidentUpdateModel)
        .where(IncidentUpdateModel.incident_id == incident_id)
        .order_by(IncidentUpdateModel.created_at.asc())
    )
    return result.scalars().all()


@router.post("/{incident_id}/resolve", response_model=IncidentResponse)
async def resolve_incident(
    incident_id: uuid.UUID,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.tenant_id == user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.status in ("resolved", "closed"):
        raise HTTPException(status_code=400, detail="Incident already resolved")

    incident.status = "resolved"
    incident.resolved_at = datetime.now(timezone.utc)

    update = IncidentUpdateModel(
        incident_id=incident.id,
        message="Incident resolved",
        update_type="resolution",
        created_by=user.id,
        new_status="resolved",
    )
    db.add(update)
    await db.commit()
    await db.refresh(incident)
    return incident


# --- Postmortem ---

@router.get("/{incident_id}/postmortem", response_model=PostmortemResponse)
async def get_postmortem(
    incident_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Postmortem).where(Postmortem.incident_id == incident_id)
    )
    postmortem = result.scalar_one_or_none()
    if not postmortem:
        raise HTTPException(status_code=404, detail="Postmortem not found")
    return postmortem


@router.post("/{incident_id}/postmortem", response_model=PostmortemResponse)
async def create_postmortem(
    incident_id: uuid.UUID,
    data: PostmortemCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(Incident).where(
            Incident.id == incident_id,
            Incident.tenant_id == user.tenant_id,
        )
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Check no existing postmortem
    result = await db.execute(
        select(Postmortem).where(Postmortem.incident_id == incident_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Postmortem already exists")

    postmortem = Postmortem(
        incident_id=incident.id,
        tenant_id=user.tenant_id,
        summary=data.summary,
        root_cause=data.root_cause,
        impact=data.impact,
        timeline=data.timeline,
        lessons_learned=data.lessons_learned,
        action_items=data.action_items,
        created_by=user.id,
    )
    db.add(postmortem)
    await db.commit()
    await db.refresh(postmortem)
    return postmortem


@router.put("/{incident_id}/postmortem", response_model=PostmortemResponse)
async def update_postmortem(
    incident_id: uuid.UUID,
    data: PostmortemCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Postmortem).where(Postmortem.incident_id == incident_id)
    )
    postmortem = result.scalar_one_or_none()
    if not postmortem:
        raise HTTPException(status_code=404, detail="Postmortem not found")

    postmortem.summary = data.summary
    postmortem.root_cause = data.root_cause
    postmortem.impact = data.impact
    postmortem.timeline = data.timeline
    postmortem.lessons_learned = data.lessons_learned
    postmortem.action_items = data.action_items

    await db.commit()
    await db.refresh(postmortem)
    return postmortem
