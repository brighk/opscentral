import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.remote_actions.models import PREDEFINED_ACTIONS

# --- Step parameters, one model per step type ---


class RemoteActionStepParams(BaseModel):
    """Queue a remote action on an agent and wait for its result."""

    agent_id: uuid.UUID
    action: str
    parameters: dict[str, Any] = {}
    timeout_seconds: int = Field(300, ge=10, le=1800)

    @field_validator("action")
    @classmethod
    def _known_action(cls, v: str) -> str:
        if v not in PREDEFINED_ACTIONS:
            raise ValueError(f"action must be one of: {', '.join(PREDEFINED_ACTIONS)}")
        return v


class WebhookStepParams(BaseModel):
    """Send an HTTP request; non-2xx responses fail the step."""

    url: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    headers: dict[str, str] = {}
    body: Any = None
    timeout_seconds: int = Field(10, ge=1, le=30)


class DelayStepParams(BaseModel):
    seconds: int = Field(0, ge=0, le=3600)


class ConditionStepParams(BaseModel):
    """Check a value from an earlier step's result; fails the step when false.

    `path` is a dot-separated path into that step's result, e.g. "status_code"
    for a webhook step or "result.returncode" for a remote action step.
    """

    step: int = Field(ge=0)
    path: str
    operator: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains"] = "eq"
    value: Any = None


STEP_PARAM_MODELS: dict[str, type[BaseModel]] = {
    "remote_action": RemoteActionStepParams,
    "webhook": WebhookStepParams,
    "delay": DelayStepParams,
    "condition": ConditionStepParams,
}


class RunbookStepSchema(BaseModel):
    name: str
    action_type: Literal["remote_action", "webhook", "delay", "condition"]
    parameters: dict[str, Any] = {}
    # stop: fail the execution. continue/skip: record the failure and go on.
    on_failure: Literal["stop", "continue", "skip"] = "stop"

    @model_validator(mode="after")
    def _validate_parameters(self) -> "RunbookStepSchema":
        model = STEP_PARAM_MODELS[self.action_type]
        # Store the normalized parameters (defaults filled in, UUIDs as strings)
        self.parameters = model.model_validate(self.parameters).model_dump(mode="json")
        return self


def _validate_step_references(steps: list[RunbookStepSchema]) -> None:
    for i, step in enumerate(steps):
        if step.action_type == "condition" and step.parameters["step"] >= i:
            raise ValueError(
                f"Step {i} ({step.name!r}): a condition can only check an earlier step"
            )


class RunbookCreate(BaseModel):
    name: str
    description: str | None = None
    steps: list[RunbookStepSchema] = Field(min_length=1)
    trigger_type: str = "manual"
    requires_approval: bool = False

    @model_validator(mode="after")
    def _check_references(self) -> "RunbookCreate":
        _validate_step_references(self.steps)
        return self


class RunbookUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[RunbookStepSchema] | None = Field(None, min_length=1)
    trigger_type: str | None = None
    requires_approval: bool | None = None
    is_enabled: bool | None = None

    @model_validator(mode="after")
    def _check_references(self) -> "RunbookUpdate":
        if self.steps is not None:
            _validate_step_references(self.steps)
        return self


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
