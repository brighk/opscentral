import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def notify_oncall(
    user_id: uuid.UUID,
    message: str,
    notification_type: str = "alert",
) -> bool:
    """Send an on-call notification to a user via email and tenant notification channels."""
    from app.config import settings

    try:
        engine = create_async_engine(settings.DATABASE_URL)
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with async_session() as db:
            from app.auth.models import User
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"notify_oncall: user {user_id} not found")
                await engine.dispose()
                return False

            title = f"On-Call Notification: {notification_type}"
            severity = "warning" if notification_type == "alert" else "info"

            from app.notifications.service import send_alert_email
            await send_alert_email(user.email, title, message, severity)

            from app.notifications.models import NotificationChannel
            from app.notifications.dispatchers import dispatch_notification

            channels_result = await db.execute(
                select(NotificationChannel).where(
                    NotificationChannel.tenant_id == user.tenant_id,
                    NotificationChannel.is_enabled.is_(True),
                )
            )
            channels = channels_result.scalars().all()

            for channel in channels:
                try:
                    await dispatch_notification(
                        channel=channel,
                        title=title,
                        message=message,
                        severity=severity,
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to dispatch on-call notification via {channel.channel_type}: {e}"
                    )

        await engine.dispose()
        logger.info(f"On-call notification sent to user {user_id}: [{notification_type}] {message}")
        return True

    except Exception as e:
        logger.error(f"notify_oncall failed for user {user_id}: {e}")
        return False
