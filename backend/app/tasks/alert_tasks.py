import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.agents.models import Agent
from app.alerting.models import Alert, AlertRule
from app.auth.models import User
from app.config import settings
from app.monitoring.models import Metric
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

SYNC_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "")


def _get_sync_session():
    engine = create_engine(SYNC_DB_URL)
    return Session(engine)


CONDITION_OPS = {
    "gt": lambda val, thresh: val > thresh,
    "gte": lambda val, thresh: val >= thresh,
    "lt": lambda val, thresh: val < thresh,
    "lte": lambda val, thresh: val <= thresh,
    "eq": lambda val, thresh: val == thresh,
}


@celery.task(name="app.tasks.alert_tasks.evaluate_alert_rules")
def evaluate_alert_rules():
    """Evaluate all enabled alert rules against recent metrics."""
    session = _get_sync_session()
    try:
        rules = (
            session.execute(
                select(AlertRule).where(AlertRule.is_enabled == True)  # noqa: E712
            )
            .scalars()
            .all()
        )

        now = datetime.now(UTC)

        for rule in rules:
            try:
                _evaluate_rule(session, rule, now)
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.id}: {e}")

        session.commit()
    finally:
        session.close()


def _evaluate_rule(session: Session, rule: AlertRule, now: datetime):
    from app.maintenance.checker import is_in_maintenance

    if is_in_maintenance(session, rule.tenant_id, agent_id=rule.agent_id):
        logger.info(f"Rule {rule.id} suppressed: in maintenance window")
        return

    lookback = now - timedelta(seconds=rule.duration_seconds)

    query = select(func.avg(Metric.metric_value)).where(
        Metric.tenant_id == rule.tenant_id,
        Metric.metric_name == rule.metric_name,
        Metric.recorded_at >= lookback,
    )
    if rule.agent_id:
        query = query.where(Metric.agent_id == rule.agent_id)

    avg_value = session.execute(query).scalar()
    if avg_value is None:
        return

    op = CONDITION_OPS.get(rule.condition)
    if not op:
        return

    condition_met = op(avg_value, rule.threshold)

    # Check for existing firing alert
    existing = session.execute(
        select(Alert).where(
            Alert.rule_id == rule.id,
            Alert.status.in_(["firing", "acknowledged"]),
        )
    ).scalar_one_or_none()

    if condition_met and not existing:
        # Fire new alert
        condition_text = f"{rule.metric_name} {rule.condition} {rule.threshold}"
        alert = Alert(
            tenant_id=rule.tenant_id,
            rule_id=rule.id,
            agent_id=rule.agent_id,
            status="firing",
            severity=rule.severity,
            title=f"{rule.name}: {condition_text}",
            message=(
                f"Metric {rule.metric_name} is {avg_value:.2f} "
                f"(threshold: {rule.condition} {rule.threshold})"
            ),
            metric_value=avg_value,
            fired_at=now,
        )
        session.add(alert)

        # Send email notification
        if rule.notify_email:
            _send_notification(session, rule, alert)

    elif not condition_met and existing:
        # Auto-resolve
        existing.status = "resolved"
        existing.resolved_at = now


def _send_notification(session: Session, rule: AlertRule, alert: Alert):
    """Send notification via email and all enabled notification channels."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Send email to all tenant users if enabled on rule
    if rule.notify_email:
        try:
            users = (
                session.execute(
                    select(User).where(User.tenant_id == rule.tenant_id, User.is_active == True)  # noqa: E712
                )
                .scalars()
                .all()
            )

            from app.notifications.service import send_alert_email

            for user in users:
                loop.run_until_complete(
                    send_alert_email(user.email, alert.title, alert.message or "", alert.severity)
                )
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")

    # Dispatch to all enabled notification channels for this tenant
    try:
        from app.notifications.dispatchers import dispatch_notification
        from app.notifications.models import NotificationChannel

        channels = (
            session.execute(
                select(NotificationChannel).where(
                    NotificationChannel.tenant_id == rule.tenant_id,
                    NotificationChannel.is_enabled == True,  # noqa: E712
                )
            )
            .scalars()
            .all()
        )

        for channel in channels:
            try:
                loop.run_until_complete(
                    dispatch_notification(
                        channel=channel,
                        title=alert.title,
                        message=alert.message or "",
                        severity=alert.severity,
                    )
                )
            except Exception as e:
                logger.error(f"Failed to dispatch to {channel.channel_type} ({channel.name}): {e}")
    except Exception as e:
        logger.error(f"Failed to load notification channels: {e}")


@celery.task(name="app.tasks.alert_tasks.detect_stale_agents")
def detect_stale_agents():
    """Detect agents that haven't sent a heartbeat recently."""
    from app.agents.status_models import AgentStatusLog

    session = _get_sync_session()
    try:
        cutoff = datetime.now(UTC) - timedelta(minutes=5)

        stale_agents = (
            session.execute(
                select(Agent).where(
                    Agent.is_active == True,  # noqa: E712
                    Agent.last_seen.is_not(None),
                    Agent.last_seen < cutoff,
                )
            )
            .scalars()
            .all()
        )

        now = datetime.now(UTC)

        for agent in stale_agents:
            # Check if alert already exists
            existing = session.execute(
                select(Alert).where(
                    Alert.tenant_id == agent.tenant_id,
                    Alert.agent_id == agent.id,
                    Alert.title.like("%Agent offline%"),
                    Alert.status.in_(["firing", "acknowledged"]),
                )
            ).scalar_one_or_none()

            if not existing:
                alert = Alert(
                    tenant_id=agent.tenant_id,
                    rule_id=None,
                    agent_id=agent.id,
                    status="firing",
                    severity="critical",
                    title=f"Agent offline: {agent.hostname}",
                    message=f"Agent {agent.hostname} last seen at {agent.last_seen}",
                    fired_at=now,
                )
                session.add(alert)

                # Record offline status transition
                last_seen = agent.last_seen.isoformat() if agent.last_seen else "never"
                session.add(
                    AgentStatusLog(
                        tenant_id=agent.tenant_id,
                        agent_id=agent.id,
                        status="offline",
                        message=f"No heartbeat since {last_seen}",
                        recorded_at=now,
                    )
                )

        session.commit()
    finally:
        session.close()
