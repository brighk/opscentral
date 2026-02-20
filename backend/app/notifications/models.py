import uuid

from sqlalchemy import Boolean, String, Text, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin


class NotificationChannel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "notification_channels"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # email, slack, teams, discord, webhook
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # config stores channel-specific settings:
    #   slack: {"webhook_url": "https://hooks.slack.com/..."}
    #   teams: {"webhook_url": "https://outlook.office.com/webhook/..."}
    #   discord: {"webhook_url": "https://discord.com/api/webhooks/..."}
    #   webhook: {"url": "https://...", "method": "POST", "headers": {}}
    #   email: {"recipients": ["a@b.com"]}
