import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Vulnerability(Base, UUIDMixin, TimestampMixin):
    """A known vulnerability affecting a software package on an asset."""

    __tablename__ = "vulnerabilities"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("assets.id"), nullable=False)
    software_name: Mapped[str] = mapped_column(String(255), nullable=False)
    software_version: Mapped[str | None] = mapped_column(String(100))
    cve_id: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. CVE-2024-1234
    severity: Mapped[str] = mapped_column(
        String(20), default="unknown"
    )  # critical, high, medium, low, unknown
    score: Mapped[float | None] = mapped_column(Float, nullable=True)  # CVSS score
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    affected_versions: Mapped[str | None] = mapped_column(Text, nullable=True)  # version range
    fixed_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_vuln_asset_cve", "asset_id", "cve_id", unique=True),
        Index("ix_vuln_tenant_severity", "tenant_id", "severity"),
    )


class VulnerabilityScan(Base, UUIDMixin, TimestampMixin):
    """Record of a vulnerability scan run."""

    __tablename__ = "vulnerability_scans"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("assets.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, completed, failed
    packages_scanned: Mapped[int] = mapped_column(Integer, default=0)
    vulnerabilities_found: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
