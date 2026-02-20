import secrets
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Boolean, Text, JSON, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin


class Agent(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "agents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("tenants.id"), nullable=False, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: secrets.token_hex(32)
    )
    os_type: Mapped[str] = mapped_column(String(50), nullable=True)
    os_version: Mapped[str] = mapped_column(String(100), nullable=True)
    agent_version: Mapped[str] = mapped_column(String(20), nullable=True)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
