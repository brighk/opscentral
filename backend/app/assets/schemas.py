import uuid
from datetime import datetime

from pydantic import BaseModel


class AssetResponse(BaseModel):
    id: uuid.UUID
    hostname: str
    asset_type: str
    os_type: str | None
    os_version: str | None
    cpu_model: str | None
    cpu_cores: int | None
    ram_total_gb: float | None
    disk_total_gb: float | None
    ip_addresses: list | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AssetDetailResponse(AssetResponse):
    agent_id: uuid.UUID | None
    mac_addresses: list | None
    system_info: dict | None
    software: list["SoftwareResponse"] = []


class SoftwareResponse(BaseModel):
    id: uuid.UUID
    name: str
    version: str | None
    publisher: str | None

    model_config = {"from_attributes": True}
