import uuid
from datetime import datetime

from pydantic import BaseModel


class MetricDataPoint(BaseModel):
    time_bucket: datetime
    avg_value: float
    min_value: float
    max_value: float

    model_config = {"from_attributes": True}


class MetricQueryParams(BaseModel):
    agent_id: uuid.UUID | None = None
    metric_name: str | None = None
    start: datetime | None = None
    end: datetime | None = None
    bucket_seconds: int = 300  # 5-minute buckets default


class StatusOverview(BaseModel):
    total_agents: int
    online_agents: int
    offline_agents: int
    total_assets: int
    active_alerts: int
    metrics_last_hour: int
