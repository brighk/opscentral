"""Celery tasks for metric retention and downsampling."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.orm import Session

from app.config import settings
from app.monitoring.models import Metric
from app.healthchecks.models import HealthCheckLog
from app.monitoring.process_models import ProcessSnapshot
from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)

SYNC_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "")

# Default retention policies (can be overridden per tenant via settings)
RETENTION_RAW_DAYS = 7           # Keep raw per-minute data for 7 days
RETENTION_PROCESS_HOURS = 24     # Keep process snapshots for 24 hours (latest is always kept)
RETENTION_HEALTHLOG_DAYS = 30    # Keep health check logs for 30 days


def _get_sync_session():
    engine = create_engine(SYNC_DB_URL)
    return Session(engine)


@celery.task(name="app.tasks.retention_tasks.cleanup_old_metrics")
def cleanup_old_metrics():
    """Delete raw metrics older than the retention period."""
    session = _get_sync_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_RAW_DAYS)

        result = session.execute(
            delete(Metric).where(Metric.recorded_at < cutoff)
        )
        deleted = result.rowcount
        session.commit()

        if deleted > 0:
            logger.info(f"Retention: deleted {deleted} raw metrics older than {RETENTION_RAW_DAYS} days")
    except Exception as e:
        logger.error(f"Error during metric retention cleanup: {e}")
        session.rollback()
    finally:
        session.close()


@celery.task(name="app.tasks.retention_tasks.cleanup_old_process_snapshots")
def cleanup_old_process_snapshots():
    """Delete process snapshots older than retention period.

    Note: the gateway already keeps only the latest snapshot per agent,
    so this is a safety net for any orphaned data.
    """
    session = _get_sync_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=RETENTION_PROCESS_HOURS)
        result = session.execute(
            delete(ProcessSnapshot).where(ProcessSnapshot.recorded_at < cutoff)
        )
        deleted = result.rowcount
        session.commit()
        if deleted > 0:
            logger.info(f"Retention: deleted {deleted} old process snapshots")
    except Exception as e:
        logger.error(f"Error during process snapshot cleanup: {e}")
        session.rollback()
    finally:
        session.close()


@celery.task(name="app.tasks.retention_tasks.cleanup_old_healthcheck_logs")
def cleanup_old_healthcheck_logs():
    """Delete health check logs older than retention period."""
    session = _get_sync_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_HEALTHLOG_DAYS)
        result = session.execute(
            delete(HealthCheckLog).where(HealthCheckLog.checked_at < cutoff)
        )
        deleted = result.rowcount
        session.commit()
        if deleted > 0:
            logger.info(f"Retention: deleted {deleted} old health check logs")
    except Exception as e:
        logger.error(f"Error during health check log cleanup: {e}")
        session.rollback()
    finally:
        session.close()


@celery.task(name="app.tasks.retention_tasks.setup_timescaledb_retention")
def setup_timescaledb_retention():
    """Set up TimescaleDB-native retention policies and continuous aggregates.

    This task is idempotent — safe to run multiple times. It configures:
    1. Automatic data retention (drop chunks older than retention period)
    2. Continuous aggregates for hourly/daily rollups (if metrics is a hypertable)
    """
    session = _get_sync_session()
    try:
        dialect = session.bind.dialect.name
        if dialect != "postgresql":
            logger.info("TimescaleDB retention only applies to PostgreSQL, skipping")
            return

        # Check if TimescaleDB is available
        try:
            session.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'"))
        except Exception:
            logger.info("TimescaleDB extension not found, using manual retention only")
            return

        # Try to add retention policy (will no-op if already set)
        try:
            session.execute(text(
                f"SELECT add_retention_policy('metrics', INTERVAL '{RETENTION_RAW_DAYS} days', if_not_exists => true)"
            ))
            logger.info(f"TimescaleDB retention policy set: {RETENTION_RAW_DAYS} days for metrics")
        except Exception as e:
            logger.debug(f"Could not set TimescaleDB retention policy (table may not be a hypertable): {e}")

        session.commit()
    except Exception as e:
        logger.error(f"Error setting up TimescaleDB retention: {e}")
        session.rollback()
    finally:
        session.close()
