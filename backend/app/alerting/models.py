import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Boolean, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin


class AlertRule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "alert_rules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    condition: Mapped[str] = mapped_column(String(10), nullable=False)  # gt, lt, gte, lte, eq
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(default=60)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="warning")  # info, warning, critical
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_email: Mapped[bool] = mapped_column(Boolean, default=True)
    runbook_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    escalation_policy_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)


class Alert(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "alerts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True
    )
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("alert_rules.id"), nullable=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="firing")  # firing, acknowledged, resolved
    severity: Mapped[str] = mapped_column(String(20), default="warning")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    metric_value: Mapped[float | None] = mapped_column(Float)
    fired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
