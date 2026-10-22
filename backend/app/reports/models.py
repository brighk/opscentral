import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Report(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "reports"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    format: Mapped[str] = mapped_column(String(10), nullable=False, default="pdf")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generating")
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class ReportSchedule(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "report_schedules"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # weekly, monthly
    recipients: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComplianceScore(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "compliance_scores"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    patching_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    uptime_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    vulnerability_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    agent_coverage_score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
