import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MaintenanceWindowCreate(BaseModel):
    name: str
    description: str | None = None
    start_time: datetime
    end_time: datetime
    scope: str = "all"
    scope_ids: list[str] = []
    is_active: bool = True


class MaintenanceWindowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    scope: str | None = None
    scope_ids: list[str] | None = None
    is_active: bool | None = None


class MaintenanceWindowResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None
    start_time: datetime
    end_time: datetime
    scope: str
    scope_ids: list[Any]
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
