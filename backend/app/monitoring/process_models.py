import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessSnapshot(Base):
    __tablename__ = "process_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("agents.id"), nullable=False)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cpu_percent: Mapped[float] = mapped_column(Float, default=0)
    memory_percent: Mapped[float] = mapped_column(Float, default=0)
    memory_mb: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(50), default="running")
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    num_threads: Mapped[int] = mapped_column(Integer, default=0)
    command: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_process_snapshots_agent_time", "agent_id", "recorded_at"),
        Index("ix_process_snapshots_tenant_time", "tenant_id", "recorded_at"),
    )
