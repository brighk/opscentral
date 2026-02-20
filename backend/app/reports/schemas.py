import uuid
from datetime import datetime

from pydantic import BaseModel


class ReportCreate(BaseModel):
    report_type: str
    format: str = "pdf"
    parameters: dict | None = None


class ReportResponse(BaseModel):
    id: uuid.UUID
    report_type: str
    format: str
    status: str
    file_path: str | None = None
    parameters: dict | None = None
    error: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportScheduleCreate(BaseModel):
    report_type: str
    frequency: str  # weekly, monthly
    recipients: list[str] | None = None


class ReportScheduleResponse(BaseModel):
    id: uuid.UUID
    report_type: str
    frequency: str
    recipients: list[str] | None = None
    is_active: bool
    next_run_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplianceScoreResponse(BaseModel):
    overall_score: float
    patching_score: float
    uptime_score: float
    vulnerability_score: float
    agent_coverage_score: float
    calculated_at: datetime

    model_config = {"from_attributes": True}
