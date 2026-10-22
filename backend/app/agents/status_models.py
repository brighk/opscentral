import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentStatusLog(Base):
    """Tracks agent online/offline transitions over time."""

    __tablename__ = "agent_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agents.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # online, offline
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (Index("ix_agent_status_logs_agent_time", "agent_id", "recorded_at"),)
