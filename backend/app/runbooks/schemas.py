import uuid
from datetime import datetime

from pydantic import BaseModel


class RunbookStepSchema(BaseModel):
    name: str
    action_type: str  # remote_action, webhook, delay, condition
    parameters: dict = {}
    on_failure: str = "stop"  # stop, continue, skip


class RunbookCreate(BaseModel):
    name: str
    description: str | None = None
    steps: list[RunbookStepSchema]
    trigger_type: str = "manual"
    requires_approval: bool = False


class RunbookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[RunbookStepSchema] | None = None
    trigger_type: str | None = None
    requires_approval: bool | None = None
    is_enabled: bool | None = None


class RunbookResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    steps: list[dict]
    trigger_type: str
    requires_approval: bool
    is_enabled: bool
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class RunbookStepExecutionResponse(BaseModel):
    id: uuid.UUID
    step_index: int
    step_name: str
    status: str
    result: dict | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class RunbookExecutionResponse(BaseModel):
    id: uuid.UUID
    runbook_id: uuid.UUID
    status: str
    triggered_by: uuid.UUID
    approved_by: uuid.UUID | None
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunbookExecuteRequest(BaseModel):
    parameters: dict = {}
