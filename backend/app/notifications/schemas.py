import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationChannelCreate(BaseModel):
    name: str
    channel_type: str  # email, slack, teams, discord, webhook
    is_enabled: bool = True
    config: dict = {}


class NotificationChannelUpdate(BaseModel):
    name: str | None = None
    is_enabled: bool | None = None
    config: dict | None = None


class NotificationChannelResponse(BaseModel):
    id: uuid.UUID
    name: str
    channel_type: str
    is_enabled: bool
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}
