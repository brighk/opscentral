import uuid
from datetime import datetime

from pydantic import BaseModel


class APIKeyCreate(BaseModel):
    name: str
    scopes: list[str] | None = None
    expires_at: datetime | None = None


class APIKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    scopes: list[str] | None
    is_active: bool
    expires_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class APIKeyCreatedResponse(APIKeyResponse):
    raw_key: str
