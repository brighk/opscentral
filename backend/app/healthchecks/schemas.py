import uuid
from datetime import datetime

from pydantic import BaseModel


class HealthCheckCreate(BaseModel):
    name: str
    check_type: str  # http, tcp, dns
    target: str
    interval_seconds: int = 60
    timeout_seconds: int = 10
    is_enabled: bool = True
    expected_status: int | None = 200
    expected_body: str | None = None
    http_method: str = "GET"
    http_headers: dict | None = None
    alert_after_failures: int = 3
    notify_channels: bool = True


class HealthCheckUpdate(BaseModel):
    name: str | None = None
    target: str | None = None
    interval_seconds: int | None = None
    timeout_seconds: int | None = None
    is_enabled: bool | None = None
    expected_status: int | None = None
    expected_body: str | None = None
    http_method: str | None = None
    http_headers: dict | None = None
    alert_after_failures: int | None = None
    notify_channels: bool | None = None


class HealthCheckResponse(BaseModel):
    id: uuid.UUID
    name: str
    check_type: str
    target: str
    interval_seconds: int
    timeout_seconds: int
    is_enabled: bool
    expected_status: int | None
    http_method: str
    alert_after_failures: int
    notify_channels: bool
    status: str
    last_checked_at: datetime | None
    last_response_time_ms: float | None
    consecutive_failures: int
    last_error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthCheckLogResponse(BaseModel):
    id: int
    check_id: uuid.UUID
    status: str
    response_time_ms: float | None
    status_code: int | None
    error: str | None
    checked_at: datetime

    model_config = {"from_attributes": True}
