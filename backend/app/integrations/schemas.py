import uuid
from datetime import datetime

from pydantic import BaseModel


class WebhookEndpointCreate(BaseModel):
    name: str
    url: str
    secret: str | None = None  # auto-generate if omitted
    event_types: list[str]


class WebhookEndpointUpdate(BaseModel):
    name: str | None = None
    url: str | None = None
    event_types: list[str] | None = None
    is_active: bool | None = None


class WebhookEndpointResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    url: str
    event_types: list[str]
    is_active: bool
    failure_count: int
    last_triggered_at: datetime | None
    last_status_code: int | None
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    endpoint_id: uuid.UUID
    event_type: str
    payload: dict
    status_code: int | None
    response_body: str | None
    duration_ms: int | None
    created_at: datetime


class ExternalIntegrationCreate(BaseModel):
    provider: str
    name: str
    config: dict


class ExternalIntegrationUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class ExternalIntegrationResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    provider: str
    name: str
    is_active: bool
    created_at: datetime


class EventTypeResponse(BaseModel):
    key: str
    description: str
