import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

SYNC_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "")


def _get_sync_session():
    engine = create_engine(SYNC_DB_URL)
    return Session(engine)


@celery.task(name="app.tasks.oncall_tasks.run_escalations")
def run_escalations():
    """Check for unacknowledged firing alerts and escalate per policy."""
    from app.alerting.models import Alert, AlertRule
    from app.oncall.models import EscalationPolicy, OnCallSchedule, OnCallOverride

    session = _get_sync_session()
    try:
        rules_with_policy = session.execute(
            select(AlertRule).where(
                AlertRule.escalation_policy_id.isnot(None),
                AlertRule.is_enabled.is_(True),
            )
        ).scalars().all()

        now = datetime.now(timezone.utc)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for rule in rules_with_policy:
            firing_alerts = session.execute(
                select(Alert).where(
                    Alert.rule_id == rule.id,
                    Alert.status == "firing",
                )
            ).scalars().all()

            if not firing_alerts:
                continue

            policy = session.execute(
                select(EscalationPolicy).where(
                    EscalationPolicy.id == rule.escalation_policy_id,
                    EscalationPolicy.is_active.is_(True),
                )
            ).scalar_one_or_none()

            if not policy:
                continue

            for alert in firing_alerts:
                if not alert.fired_at:
                    continue

                fired_at = alert.fired_at
                if fired_at.tzinfo is None:
                    fired_at = fired_at.replace(tzinfo=timezone.utc)
                elapsed_minutes = (now - fired_at).total_seconds() / 60

                for step in policy.steps:
                    delay_minutes = step.get("delay_minutes", 0)
                    if elapsed_minutes < delay_minutes:
                        continue

                    for target in step.get("targets", []):
                        target_type = target.get("type")
                        target_id = target.get("id")
                        if not target_id:
                            continue

                        try:
                            target_uuid = uuid.UUID(target_id)
                        except ValueError:
                            logger.error(f"Invalid target UUID: {target_id}")
                            continue

                        if target_type == "user":
                            _notify_user(loop, target_uuid, alert, elapsed_minutes)
                        elif target_type == "schedule":
                            _notify_schedule_oncall(
                                loop, session, target_uuid, alert, elapsed_minutes, now
                            )

        session.commit()
    except Exception as e:
        logger.error(f"run_escalations failed: {e}")
    finally:
        session.close()


def _notify_user(loop, user_id: uuid.UUID, alert, elapsed_minutes: float):
    from app.oncall.notifier import notify_oncall

    message = (
        f"ESCALATION: Alert '{alert.title}' has been firing for "
        f"{int(elapsed_minutes)} minutes. Severity: {alert.severity}. "
        f"Message: {alert.message or ''}"
    )
    try:
        loop.run_until_complete(notify_oncall(user_id, message, notification_type="alert"))
    except Exception as e:
        logger.error(f"Failed to escalate to user {user_id}: {e}")


def _notify_schedule_oncall(
    loop, session: Session, schedule_id: uuid.UUID, alert, elapsed_minutes: float, now: datetime
):
    """Resolve the current on-call user for a schedule and notify them."""
    from app.oncall.models import OnCallSchedule, OnCallOverride

    override = session.execute(
        select(OnCallOverride)
        .where(
            OnCallOverride.schedule_id == schedule_id,
            OnCallOverride.start_time <= now,
            OnCallOverride.end_time >= now,
        )
        .order_by(OnCallOverride.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if override:
        user_id_str = str(override.user_id)
    else:
        schedule = session.execute(
            select(OnCallSchedule).where(OnCallSchedule.id == schedule_id)
        ).scalar_one_or_none()

        if not schedule or not schedule.participants:
            return

        participants = schedule.participants
        epoch = schedule.created_at
        if epoch.tzinfo is None:
            epoch = epoch.replace(tzinfo=timezone.utc)
        elapsed = now - epoch

        if schedule.rotation_type == "daily":
            index = elapsed.days % len(participants)
        elif schedule.rotation_type == "weekly":
            index = (elapsed.days // 7) % len(participants)
        elif schedule.rotation_type == "biweekly":
            index = (elapsed.days // 14) % len(participants)
        else:
            index = 0

        user_id_str = str(participants[index])

    try:
        target_uuid = uuid.UUID(user_id_str)
    except ValueError:
        logger.error(f"Invalid on-call user UUID: {user_id_str}")
        return

    _notify_user(loop, target_uuid, alert, elapsed_minutes)


@celery.task(name="app.tasks.oncall_tasks.send_handoff_notifications")
def send_handoff_notifications():
    """Notify on-call rotation handoffs when the current on-call user changes."""
    from app.oncall.models import OnCallSchedule, OnCallOverride

    session = _get_sync_session()
    try:
        schedules = session.execute(
            select(OnCallSchedule).where(OnCallSchedule.is_active.is_(True))
        ).scalars().all()

        now = datetime.now(timezone.utc)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        for schedule in schedules:
            override = session.execute(
                select(OnCallOverride)
                .where(
                    OnCallOverride.schedule_id == schedule.id,
                    OnCallOverride.start_time <= now,
                    OnCallOverride.end_time >= now,
                )
                .order_by(OnCallOverride.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            if override:
                current_user_id = str(override.user_id)
            elif schedule.participants:
                participants = schedule.participants
                epoch = schedule.created_at
                if epoch.tzinfo is None:
                    epoch = epoch.replace(tzinfo=timezone.utc)
                elapsed = now - epoch

                if schedule.rotation_type == "daily":
                    index = elapsed.days % len(participants)
                elif schedule.rotation_type == "weekly":
                    index = (elapsed.days // 7) % len(participants)
                elif schedule.rotation_type == "biweekly":
                    index = (elapsed.days // 14) % len(participants)
                else:
                    index = 0

                current_user_id = str(participants[index])
            else:
                continue

            previous_user_id = schedule.last_oncall_user_id

            if previous_user_id != current_user_id:
                if previous_user_id:
                    try:
                        prev_uuid = uuid.UUID(previous_user_id)
                        msg = (
                            f"Your on-call shift for schedule '{schedule.name}' has ended. "
                            f"The next person is now on call."
                        )
                        loop.run_until_complete(
                            _async_notify(prev_uuid, msg, "handoff")
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify outgoing user {previous_user_id}: {e}")

                try:
                    curr_uuid = uuid.UUID(current_user_id)
                    msg = (
                        f"You are now on call for schedule '{schedule.name}'. "
                        f"Please ensure you are available to respond to alerts."
                    )
                    loop.run_until_complete(
                        _async_notify(curr_uuid, msg, "handoff")
                    )
                except Exception as e:
                    logger.error(f"Failed to notify incoming user {current_user_id}: {e}")

                schedule.last_oncall_user_id = current_user_id

        session.commit()
    except Exception as e:
        logger.error(f"send_handoff_notifications failed: {e}")
    finally:
        session.close()


async def _async_notify(user_id: uuid.UUID, message: str, notification_type: str):
    from app.oncall.notifier import notify_oncall
    await notify_oncall(user_id, message, notification_type=notification_type)
