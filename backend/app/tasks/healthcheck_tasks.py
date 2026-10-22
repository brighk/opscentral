"""Celery tasks for executing service health checks."""

import asyncio
import logging
import socket
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.alerting.models import Alert
from app.config import settings
from app.healthchecks.models import HealthCheck, HealthCheckLog
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

SYNC_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "")


def _get_sync_session():
    engine = create_engine(SYNC_DB_URL)
    return Session(engine)


@celery.task(name="app.tasks.healthcheck_tasks.run_health_checks")
def run_health_checks():
    """Execute all enabled health checks that are due."""
    session = _get_sync_session()
    try:
        checks = (
            session.execute(
                select(HealthCheck).where(HealthCheck.is_enabled == True)  # noqa: E712
            )
            .scalars()
            .all()
        )

        now = datetime.now(UTC)

        for check in checks:
            # Skip if not due yet
            if check.last_checked_at:
                next_run = check.last_checked_at.timestamp() + check.interval_seconds
                if now.timestamp() < next_run:
                    continue

            try:
                _execute_check(session, check, now)
            except Exception as e:
                logger.error(f"Error executing health check {check.id}: {e}")

        session.commit()
    finally:
        session.close()


def _execute_check(session: Session, check: HealthCheck, now: datetime):
    """Execute a single health check and record results."""
    result = _run_check(check)

    check.last_checked_at = now
    check.last_response_time_ms = result["response_time_ms"]
    check.last_error = result.get("error")

    # Record log
    log = HealthCheckLog(
        check_id=check.id,
        tenant_id=check.tenant_id,
        status=result["status"],
        response_time_ms=result["response_time_ms"],
        status_code=result.get("status_code"),
        error=result.get("error"),
        checked_at=now,
    )
    session.add(log)

    if result["status"] == "up":
        # Reset failures, update status
        if check.status == "down":
            # Service recovered — auto-resolve any firing alerts
            _resolve_healthcheck_alert(session, check, now)
        check.status = "up"
        check.consecutive_failures = 0
    else:
        check.consecutive_failures += 1
        if check.consecutive_failures >= check.alert_after_failures and check.status != "down":
            check.status = "down"
            _fire_healthcheck_alert(session, check, now)


def _run_check(check: HealthCheck) -> dict:
    """Run the actual check and return result dict."""
    if check.check_type == "http":
        return _check_http(check)
    elif check.check_type == "tcp":
        return _check_tcp(check)
    elif check.check_type == "dns":
        return _check_dns(check)
    else:
        return {
            "status": "down",
            "response_time_ms": 0,
            "error": f"Unknown check type: {check.check_type}",
        }


def _check_http(check: HealthCheck) -> dict:
    """HTTP health check."""
    start = time.monotonic()
    try:
        with httpx.Client(timeout=check.timeout_seconds) as client:
            resp = client.request(
                check.http_method,
                check.target,
                headers=check.http_headers or {},
            )
            elapsed_ms = (time.monotonic() - start) * 1000

            status_ok = True
            if check.expected_status and resp.status_code != check.expected_status:
                status_ok = False

            if check.expected_body and check.expected_body not in resp.text:
                status_ok = False

            return {
                "status": "up" if status_ok else "down",
                "response_time_ms": round(elapsed_ms, 2),
                "status_code": resp.status_code,
                "error": None
                if status_ok
                else f"Expected status {check.expected_status}, got {resp.status_code}",
            }
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "status": "down",
            "response_time_ms": round(elapsed_ms, 2),
            "error": str(e),
        }


def _check_tcp(check: HealthCheck) -> dict:
    """TCP port check. Target format: host:port"""
    start = time.monotonic()
    try:
        parts = check.target.rsplit(":", 1)
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 80

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(check.timeout_seconds)
        sock.connect((host, port))
        sock.close()
        elapsed_ms = (time.monotonic() - start) * 1000
        return {"status": "up", "response_time_ms": round(elapsed_ms, 2)}
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {"status": "down", "response_time_ms": round(elapsed_ms, 2), "error": str(e)}


def _check_dns(check: HealthCheck) -> dict:
    """DNS resolution check. Target is a hostname."""
    start = time.monotonic()
    try:
        socket.setdefaulttimeout(check.timeout_seconds)
        result = socket.getaddrinfo(check.target, None)
        elapsed_ms = (time.monotonic() - start) * 1000
        if result:
            return {"status": "up", "response_time_ms": round(elapsed_ms, 2)}
        return {
            "status": "down",
            "response_time_ms": round(elapsed_ms, 2),
            "error": "No DNS records found",
        }
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return {"status": "down", "response_time_ms": round(elapsed_ms, 2), "error": str(e)}


def _fire_healthcheck_alert(session: Session, check: HealthCheck, now: datetime):
    """Create an alert when a health check fails."""
    from app.maintenance.checker import is_in_maintenance

    if is_in_maintenance(session, check.tenant_id, check_id=check.id):
        logger.info(f"Health check {check.id} alert suppressed: in maintenance window")
        return

    alert = Alert(
        tenant_id=check.tenant_id,
        rule_id=None,
        agent_id=None,
        status="firing",
        severity="critical",
        title=f"Service down: {check.name}",
        message=f"Health check '{check.name}' ({check.check_type}://{check.target}) "
        f"failed {check.consecutive_failures} consecutive times. "
        f"Error: {check.last_error}",
        fired_at=now,
    )
    session.add(alert)

    # Dispatch to notification channels
    if check.notify_channels:
        try:
            from app.notifications.dispatchers import dispatch_notification
            from app.notifications.models import NotificationChannel

            channels = (
                session.execute(
                    select(NotificationChannel).where(
                        NotificationChannel.tenant_id == check.tenant_id,
                        NotificationChannel.is_enabled == True,  # noqa: E712
                    )
                )
                .scalars()
                .all()
            )

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
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
                    logger.error(f"Failed to dispatch healthcheck alert: {e}")
        except Exception as e:
            logger.error(f"Failed to send healthcheck notifications: {e}")


def _resolve_healthcheck_alert(session: Session, check: HealthCheck, now: datetime):
    """Auto-resolve firing alerts for a recovered health check."""
    existing = (
        session.execute(
            select(Alert).where(
                Alert.tenant_id == check.tenant_id,
                Alert.title.like(f"%{check.name}%"),
                Alert.status.in_(["firing", "acknowledged"]),
            )
        )
        .scalars()
        .all()
    )

    for alert in existing:
        alert.status = "resolved"
        alert.resolved_at = now
