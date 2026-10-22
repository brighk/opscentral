import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.oncall.models import EscalationPolicy, OnCallOverride, OnCallSchedule
from app.oncall.resolver import get_current_oncall
from app.oncall.schemas import (
    CurrentOnCallResponse,
    EscalationPolicyCreate,
    EscalationPolicyResponse,
    EscalationPolicyUpdate,
    OnCallOverrideCreate,
    OnCallOverrideResponse,
    OnCallScheduleCreate,
    OnCallScheduleResponse,
    OnCallScheduleUpdate,
)

router = APIRouter(prefix="/api/v1/oncall", tags=["oncall"])


# --- Schedules ---


@router.get("/schedules", response_model=list[OnCallScheduleResponse])
async def list_schedules(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnCallSchedule)
        .where(OnCallSchedule.tenant_id == user.tenant_id)
        .order_by(OnCallSchedule.created_at.desc())
    )
    return result.scalars().all()


@router.post("/schedules", response_model=OnCallScheduleResponse)
async def create_schedule(
    data: OnCallScheduleCreate,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    schedule = OnCallSchedule(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        rotation_type=data.rotation_type,
        participants=data.participants,
        handoff_time=data.handoff_time,
        handoff_day=data.handoff_day,
        timezone=data.timezone,
        created_by=user.id,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.get("/schedules/{schedule_id}", response_model=OnCallScheduleResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnCallSchedule).where(
            OnCallSchedule.id == schedule_id,
            OnCallSchedule.tenant_id == user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.put("/schedules/{schedule_id}", response_model=OnCallScheduleResponse)
async def update_schedule(
    schedule_id: uuid.UUID,
    data: OnCallScheduleUpdate,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnCallSchedule).where(
            OnCallSchedule.id == schedule_id,
            OnCallSchedule.tenant_id == user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if data.name is not None:
        schedule.name = data.name
    if data.description is not None:
        schedule.description = data.description
    if data.rotation_type is not None:
        schedule.rotation_type = data.rotation_type
    if data.participants is not None:
        schedule.participants = data.participants
    if data.handoff_time is not None:
        schedule.handoff_time = data.handoff_time
    if data.handoff_day is not None:
        schedule.handoff_day = data.handoff_day
    if data.timezone is not None:
        schedule.timezone = data.timezone
    if data.is_active is not None:
        schedule.is_active = data.is_active

    await db.commit()
    await db.refresh(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(
    schedule_id: uuid.UUID,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnCallSchedule).where(
            OnCallSchedule.id == schedule_id,
            OnCallSchedule.tenant_id == user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await db.delete(schedule)
    await db.commit()
    return {"detail": "Schedule deleted"}


@router.get("/schedules/{schedule_id}/current", response_model=CurrentOnCallResponse)
async def get_current(
    schedule_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnCallSchedule).where(
            OnCallSchedule.id == schedule_id,
            OnCallSchedule.tenant_id == user.tenant_id,
        )
    )
    schedule = result.scalar_one_or_none()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    user_id, is_override = await get_current_oncall(db, schedule_id)
    return CurrentOnCallResponse(
        schedule_id=schedule.id,
        schedule_name=schedule.name,
        user_id=user_id,
        is_override=is_override,
    )


# --- Overrides ---


@router.get("/schedules/{schedule_id}/overrides", response_model=list[OnCallOverrideResponse])
async def list_overrides(
    schedule_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnCallOverride)
        .where(OnCallOverride.schedule_id == schedule_id)
        .order_by(OnCallOverride.start_time.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("/schedules/{schedule_id}/overrides", response_model=OnCallOverrideResponse)
async def create_override(
    schedule_id: uuid.UUID,
    data: OnCallOverrideCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    # Verify schedule
    result = await db.execute(
        select(OnCallSchedule).where(
            OnCallSchedule.id == schedule_id,
            OnCallSchedule.tenant_id == user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Schedule not found")

    override = OnCallOverride(
        schedule_id=schedule_id,
        tenant_id=user.tenant_id,
        user_id=data.user_id,
        start_time=data.start_time,
        end_time=data.end_time,
        reason=data.reason,
        created_by=user.id,
    )
    db.add(override)
    await db.commit()
    await db.refresh(override)
    return override


@router.delete("/overrides/{override_id}")
async def delete_override(
    override_id: uuid.UUID,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(OnCallOverride).where(
            OnCallOverride.id == override_id,
            OnCallOverride.tenant_id == user.tenant_id,
        )
    )
    override = result.scalar_one_or_none()
    if not override:
        raise HTTPException(status_code=404, detail="Override not found")

    await db.delete(override)
    await db.commit()
    return {"detail": "Override deleted"}


# --- Escalation Policies ---


@router.get("/policies", response_model=list[EscalationPolicyResponse])
async def list_policies(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EscalationPolicy)
        .where(EscalationPolicy.tenant_id == user.tenant_id)
        .order_by(EscalationPolicy.created_at.desc())
    )
    return result.scalars().all()


@router.post("/policies", response_model=EscalationPolicyResponse)
async def create_policy(
    data: EscalationPolicyCreate,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    policy = EscalationPolicy(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        steps=[s.model_dump() for s in data.steps],
        repeat_count=data.repeat_count,
        created_by=user.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return policy


@router.get("/policies/{policy_id}", response_model=EscalationPolicyResponse)
async def get_policy(
    policy_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EscalationPolicy).where(
            EscalationPolicy.id == policy_id,
            EscalationPolicy.tenant_id == user.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.put("/policies/{policy_id}", response_model=EscalationPolicyResponse)
async def update_policy(
    policy_id: uuid.UUID,
    data: EscalationPolicyUpdate,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EscalationPolicy).where(
            EscalationPolicy.id == policy_id,
            EscalationPolicy.tenant_id == user.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    if data.name is not None:
        policy.name = data.name
    if data.description is not None:
        policy.description = data.description
    if data.steps is not None:
        policy.steps = [s.model_dump() for s in data.steps]
    if data.repeat_count is not None:
        policy.repeat_count = data.repeat_count
    if data.is_active is not None:
        policy.is_active = data.is_active

    await db.commit()
    await db.refresh(policy)
    return policy


@router.delete("/policies/{policy_id}")
async def delete_policy(
    policy_id: uuid.UUID,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EscalationPolicy).where(
            EscalationPolicy.id == policy_id,
            EscalationPolicy.tenant_id == user.tenant_id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    await db.delete(policy)
    await db.commit()
    return {"detail": "Policy deleted"}


@router.get("/whoami", response_model=list[CurrentOnCallResponse])
async def whoami(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Find all schedules where the current user is on call."""
    result = await db.execute(
        select(OnCallSchedule).where(
            OnCallSchedule.tenant_id == user.tenant_id,
            OnCallSchedule.is_active.is_(True),
        )
    )
    schedules = result.scalars().all()
    on_call_for = []
    for schedule in schedules:
        current_user_id, is_override = await get_current_oncall(db, schedule.id)
        if current_user_id == str(user.id):
            on_call_for.append(
                CurrentOnCallResponse(
                    schedule_id=schedule.id,
                    schedule_name=schedule.name,
                    user_id=current_user_id,
                    is_override=is_override,
                )
            )
    return on_call_for
