import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.maintenance.models import MaintenanceWindow

logger = logging.getLogger(__name__)


def is_in_maintenance(
    session: Session,
    tenant_id: uuid.UUID,
    agent_id: uuid.UUID | None = None,
    check_id: uuid.UUID | None = None,
) -> bool:
    """Returns True if currently in a maintenance window that covers this resource."""
    now = datetime.now(UTC)

    try:
        windows = (
            session.execute(
                select(MaintenanceWindow).where(
                    MaintenanceWindow.tenant_id == tenant_id,
                    MaintenanceWindow.is_active.is_(True),
                    MaintenanceWindow.start_time <= now,
                    MaintenanceWindow.end_time >= now,
                )
            )
            .scalars()
            .all()
        )
    except Exception as e:
        logger.error(f"Failed to query maintenance windows: {e}")
        return False

    for window in windows:
        scope = window.scope
        scope_ids = window.scope_ids or []

        if scope == "all":
            return True

        if (
            scope == "agents"
            and agent_id is not None
            and (not scope_ids or str(agent_id) in scope_ids)
        ):
            return True

        if (
            scope == "health_checks"
            and check_id is not None
            and (not scope_ids or str(check_id) in scope_ids)
        ):
            return True

    return False
