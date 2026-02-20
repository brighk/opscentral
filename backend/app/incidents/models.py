import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin


class Incident(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "incidents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="warning"
    )  # info, warning, critical, major
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="open"
    )  # open, investigating, identified, monitoring, resolved, closed
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # manual, alert, monitoring
    alert_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    commander_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class IncidentUpdate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "incident_updates"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    update_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="update"
    )  # update, status_change, assignment, resolution
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    new_status: Mapped[str | None] = mapped_column(String(30), nullable=True)


class IncidentTag(Base, UUIDMixin):
    __tablename__ = "incident_tags"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


class Postmortem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "postmortems"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    root_cause: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[str | None] = mapped_column(Text)
    timeline: Mapped[str | None] = mapped_column(Text)
    lessons_learned: Mapped[str | None] = mapped_column(Text)
    action_items: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
