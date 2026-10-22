import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class HealthCheck(Base, UUIDMixin, TimestampMixin):
    """A configured health check that runs on a schedule."""

    __tablename__ = "health_checks"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    check_type: Mapped[str] = mapped_column(String(20), nullable=False)  # http, tcp, dns
    target: Mapped[str] = mapped_column(
        String(500), nullable=False
    )  # URL, host:port, or domain name
    interval_seconds: Mapped[int] = mapped_column(Integer, default=60)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # http-specific
    expected_status: Mapped[int | None] = mapped_column(Integer, nullable=True, default=200)
    expected_body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    http_method: Mapped[str] = mapped_column(String(10), default="GET")
    http_headers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Alert config
    alert_after_failures: Mapped[int] = mapped_column(Integer, default=3)
    notify_channels: Mapped[bool] = mapped_column(Boolean, default=True)
    # State
    status: Mapped[str] = mapped_column(String(20), default="unknown")  # up, down, unknown
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class HealthCheckLog(Base):
    """Log of health check results over time."""

    __tablename__ = "health_check_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    check_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # up, down
    response_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
