import uuid
from datetime import datetime

from pydantic import BaseModel


class AgentRegisterRequest(BaseModel):
    hostname: str
    display_name: str | None = None
    os_type: str | None = None
    os_version: str | None = None
    agent_version: str | None = None


class AgentRegisterResponse(BaseModel):
    agent_id: uuid.UUID
    api_key: str

    model_config = {"from_attributes": True}


class AgentResponse(BaseModel):
    id: uuid.UUID
    hostname: str
    display_name: str | None
    os_type: str | None
    os_version: str | None
    agent_version: str | None
    ip_address: str | None
    last_seen: datetime | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class HeartbeatRequest(BaseModel):
    agent_version: str | None = None
    ip_address: str | None = None


class MetricsPayload(BaseModel):
    metrics: list[dict]


class InventoryPayload(BaseModel):
    system_info: dict
    software: list[dict] | None = None


class ProcessesPayload(BaseModel):
    processes: list[dict]
