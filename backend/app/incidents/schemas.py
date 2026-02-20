import uuid
from datetime import datetime

from pydantic import BaseModel


class IncidentCreate(BaseModel):
    title: str
    description: str | None = None
    severity: str = "warning"
    source: str = "manual"
    alert_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    commander_id: uuid.UUID | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    status: str | None = None
    assigned_to: uuid.UUID | None = None
    commander_id: uuid.UUID | None = None


class IncidentResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    severity: str
    status: str
    source: str
    alert_id: uuid.UUID | None
    assigned_to: uuid.UUID | None
    commander_id: uuid.UUID | None
    created_by: uuid.UUID
    resolved_at: datetime | None
    closed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentUpdateCreate(BaseModel):
    message: str
    update_type: str = "update"
    new_status: str | None = None


class IncidentUpdateResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    message: str
    update_type: str
    created_by: uuid.UUID
    new_status: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PostmortemCreate(BaseModel):
    summary: str
    root_cause: str | None = None
    impact: str | None = None
    timeline: str | None = None
    lessons_learned: str | None = None
    action_items: str | None = None


class PostmortemResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    summary: str
    root_cause: str | None
    impact: str | None
    timeline: str | None
    lessons_learned: str | None
    action_items: str | None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class IncidentStatsResponse(BaseModel):
    total: int
    open: int
    investigating: int
    resolved: int
    closed: int
    mttr_hours: float | None = None
