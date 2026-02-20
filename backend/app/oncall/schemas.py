import uuid
from datetime import datetime

from pydantic import BaseModel


class OnCallScheduleCreate(BaseModel):
    name: str
    description: str | None = None
    rotation_type: str = "weekly"
    participants: list[str] = []  # list of user IDs
    handoff_time: str = "09:00"
    handoff_day: int = 1
    timezone: str = "UTC"


class OnCallScheduleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rotation_type: str | None = None
    participants: list[str] | None = None
    handoff_time: str | None = None
    handoff_day: int | None = None
    timezone: str | None = None
    is_active: bool | None = None


class OnCallScheduleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    rotation_type: str
    participants: list
    handoff_time: str
    handoff_day: int
    timezone: str
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class OnCallOverrideCreate(BaseModel):
    user_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    reason: str | None = None


class OnCallOverrideResponse(BaseModel):
    id: uuid.UUID
    schedule_id: uuid.UUID
    user_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    reason: str | None
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class EscalationStepSchema(BaseModel):
    delay_minutes: int = 5
    targets: list[dict] = []  # [{"type": "schedule"|"user", "id": "..."}]


class EscalationPolicyCreate(BaseModel):
    name: str
    description: str | None = None
    steps: list[EscalationStepSchema] = []
    repeat_count: int = 0


class EscalationPolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[EscalationStepSchema] | None = None
    repeat_count: int | None = None
    is_active: bool | None = None


class EscalationPolicyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    steps: list
    repeat_count: int
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class CurrentOnCallResponse(BaseModel):
    schedule_id: uuid.UUID
    schedule_name: str
    user_id: str | None
    is_override: bool = False
