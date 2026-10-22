import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, TimestampMixin, UUIDMixin


class Runbook(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "runbooks"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual"
    )  # manual, alert, scheduled
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)


class RunbookExecution(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "runbook_executions"

    runbook_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("runbooks.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending_approval"
    )  # pending_approval, approved, running, completed, failed, cancelled
    triggered_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunbookStepExecution(Base, UUIDMixin):
    __tablename__ = "runbook_step_executions"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("runbook_executions.id", ondelete="CASCADE"), nullable=False
    )
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, running, completed, failed, skipped
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
