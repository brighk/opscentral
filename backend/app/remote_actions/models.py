import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, Uuid, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


PREDEFINED_ACTIONS = {
    "restart_service": {
        "name": "Restart Service",
        "description": "Restart a system service by name",
        "parameters_schema": {"service_name": "string"},
        "min_role": "operator",
    },
    "collect_diagnostics": {
        "name": "Collect Diagnostics",
        "description": "Collect system diagnostic information",
        "parameters_schema": {},
        "min_role": "operator",
    },
    "update_agent": {
        "name": "Update Agent",
        "description": "Update the OpsCentral agent to the latest version",
        "parameters_schema": {},
        "min_role": "operator",
    },
    "health_check": {
        "name": "Health Check",
        "description": "Run a comprehensive health check on the agent",
        "parameters_schema": {},
        "min_role": "operator",
    },
    "custom_script": {
        "name": "Custom Script",
        "description": "Run a custom script (admin only)",
        "parameters_schema": {"script": "string", "timeout": "integer"},
        "min_role": "admin",
    },
}


class RemoteAction(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "remote_actions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, dispatched, running, completed, failed, expired
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
