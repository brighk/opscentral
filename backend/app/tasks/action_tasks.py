import logging
from datetime import datetime, timezone

from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.action_tasks.expire_stale_actions")
def expire_stale_actions():
    """Expire actions that have passed their expiration time."""
    from sqlalchemy import create_engine, select, update
    from sqlalchemy.orm import Session

    from app.config import settings
    from app.remote_actions.models import RemoteAction

    engine = create_engine(settings.DATABASE_URL_SYNC)
    now = datetime.now(timezone.utc)

    with Session(engine) as db:
        result = db.execute(
            update(RemoteAction)
            .where(
                RemoteAction.status.in_(["pending", "dispatched"]),
                RemoteAction.expires_at <= now,
            )
            .values(
                status="expired",
                error="Action expired before completion",
                completed_at=now,
            )
        )
        db.commit()
        count = result.rowcount
        if count:
            logger.info(f"Expired {count} stale actions")

    engine.dispose()
