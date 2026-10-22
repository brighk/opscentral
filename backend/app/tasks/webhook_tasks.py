from datetime import UTC, datetime, timedelta

from app.tasks.celery_app import celery


@celery.task(name="app.tasks.webhook_tasks.cleanup_old_deliveries")
def cleanup_old_deliveries():
    """Delete webhook deliveries older than 30 days."""
    from sqlalchemy import create_engine, delete
    from sqlalchemy.orm import Session

    from app.config import settings
    from app.integrations.models import WebhookDelivery

    sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)

    cutoff = datetime.now(UTC) - timedelta(days=30)
    with Session(engine) as session:
        session.execute(delete(WebhookDelivery).where(WebhookDelivery.created_at < cutoff))
        session.commit()
    engine.dispose()
