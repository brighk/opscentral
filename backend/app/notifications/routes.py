import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.db.session import get_db
from app.dependencies import get_current_user
from app.exceptions import NotFoundError
from app.notifications.models import NotificationChannel
from app.notifications.schemas import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_channels(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationChannel)
        .where(NotificationChannel.tenant_id == user.tenant_id)
        .order_by(NotificationChannel.created_at.desc())
    )
    return result.scalars().all()


@router.post("/channels", response_model=NotificationChannelResponse)
async def create_channel(
    body: NotificationChannelCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    channel = NotificationChannel(
        tenant_id=user.tenant_id,
        name=body.name,
        channel_type=body.channel_type,
        is_enabled=body.is_enabled,
        config=body.config,
    )
    db.add(channel)
    await db.flush()
    return channel


@router.put("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: uuid.UUID,
    body: NotificationChannelUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.tenant_id == user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise NotFoundError("Notification channel not found")

    if body.name is not None:
        channel.name = body.name
    if body.is_enabled is not None:
        channel.is_enabled = body.is_enabled
    if body.config is not None:
        channel.config = body.config
    return channel


@router.delete("/channels/{channel_id}")
async def delete_channel(
    channel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.tenant_id == user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise NotFoundError("Notification channel not found")

    await db.delete(channel)
    return {"status": "deleted"}


@router.post("/channels/{channel_id}/test")
async def test_channel(
    channel_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a test notification through the specified channel."""
    result = await db.execute(
        select(NotificationChannel).where(
            NotificationChannel.id == channel_id,
            NotificationChannel.tenant_id == user.tenant_id,
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise NotFoundError("Notification channel not found")

    from app.notifications.dispatchers import dispatch_notification

    success = await dispatch_notification(
        channel=channel,
        title="Test Notification",
        message="This is a test notification from OpsCentral.",
        severity="info",
    )
    return {"status": "sent" if success else "failed"}
