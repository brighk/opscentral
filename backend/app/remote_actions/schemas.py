import uuid
from datetime import datetime

from pydantic import BaseModel


class RemoteActionCreate(BaseModel):
    agent_id: uuid.UUID
    action_type: str
    parameters: dict | None = None


class RemoteActionResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    action_type: str
    status: str
    parameters: dict | None = None
    result: dict | None = None
    error: str | None = None
    expires_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ActionTypeResponse(BaseModel):
    key: str
    name: str
    description: str
    min_role: str


class ActionResultSubmission(BaseModel):
    status: str  # completed or failed
    result: dict | None = None
    error: str | None = None
