import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.oncall.models import OnCallSchedule, OnCallOverride


async def get_current_oncall(
    db: AsyncSession,
    schedule_id: uuid.UUID,
) -> tuple[str | None, bool]:
    """Returns (user_id, is_override) for who is currently on call."""
    now = datetime.now(timezone.utc)

    # Check for active overrides first
    result = await db.execute(
        select(OnCallOverride)
        .where(
            OnCallOverride.schedule_id == schedule_id,
            OnCallOverride.start_time <= now,
            OnCallOverride.end_time >= now,
        )
        .order_by(OnCallOverride.created_at.desc())
        .limit(1)
    )
    override = result.scalar_one_or_none()
    if override:
        return str(override.user_id), True

    # Fall back to schedule rotation
    result = await db.execute(
        select(OnCallSchedule).where(OnCallSchedule.id == schedule_id)
    )
    schedule = result.scalar_one_or_none()
    if not schedule or not schedule.participants:
        return None, False

    participants = schedule.participants
    if not participants:
        return None, False

    # Calculate current rotation index based on rotation type
    rotation_type = schedule.rotation_type
    epoch = schedule.created_at.replace(tzinfo=timezone.utc) if schedule.created_at.tzinfo is None else schedule.created_at
    elapsed = now - epoch

    if rotation_type == "daily":
        index = elapsed.days % len(participants)
    elif rotation_type == "weekly":
        index = (elapsed.days // 7) % len(participants)
    elif rotation_type == "biweekly":
        index = (elapsed.days // 14) % len(participants)
    else:
        index = 0

    return str(participants[index]), False
