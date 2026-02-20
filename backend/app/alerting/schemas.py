import uuid
from datetime import datetime

from pydantic import BaseModel


class AlertRuleCreate(BaseModel):
    name: str
    description: str | None = None
    metric_name: str
    condition: str  # gt, lt, gte, lte, eq
    threshold: float
    duration_seconds: int = 60
    agent_id: uuid.UUID | None = None
    severity: str = "warning"
    notify_email: bool = True
    runbook_id: uuid.UUID | None = None
    escalation_policy_id: uuid.UUID | None = None


class AlertRuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    threshold: float | None = None
    condition: str | None = None
    severity: str | None = None
    is_enabled: bool | None = None
    notify_email: bool | None = None
    runbook_id: uuid.UUID | None = None
    escalation_policy_id: uuid.UUID | None = None


class AlertRuleResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    metric_name: str
    condition: str
    threshold: float
    duration_seconds: int
    agent_id: uuid.UUID | None
    severity: str
    is_enabled: bool
    notify_email: bool
    runbook_id: uuid.UUID | None = None
    escalation_policy_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    id: uuid.UUID
    rule_id: uuid.UUID
    agent_id: uuid.UUID | None
    status: str
    severity: str
    title: str
    message: str | None
    metric_value: float | None
    fired_at: datetime
    resolved_at: datetime | None
    acknowledged_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
