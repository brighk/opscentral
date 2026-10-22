import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class OnCallSchedule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "oncall_schedules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    rotation_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="weekly"
    )  # daily, weekly, biweekly, custom
    participants: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    handoff_time: Mapped[str] = mapped_column(
        String(5), nullable=False, default="09:00"
    )  # HH:MM format
    handoff_day: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 0=Mon, 6=Sun
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    last_oncall_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)


class OnCallOverride(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "oncall_overrides"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("oncall_schedules.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)


class EscalationPolicy(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "escalation_policies"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # steps: [{"delay_minutes": 5, "targets": [{"type": "schedule"|"user", "id": "..."}]}]
    repeat_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
