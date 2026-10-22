import logging
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import CursorResult

from app.tasks.celery_app import celery

logger = logging.getLogger(__name__)


@celery.task(name="app.tasks.action_tasks.expire_stale_actions")
def expire_stale_actions():
    """Expire actions that have passed their expiration time."""
    from sqlalchemy import create_engine, update
    from sqlalchemy.orm import Session

    from app.config import settings
    from app.remote_actions.models import RemoteAction

    engine = create_engine(settings.DATABASE_URL_SYNC)
    now = datetime.now(UTC)

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
        count = cast(CursorResult, result).rowcount
        if count:
            logger.info(f"Expired {count} stale actions")

    engine.dispose()
