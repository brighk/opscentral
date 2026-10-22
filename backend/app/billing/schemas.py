import uuid
from datetime import datetime

from pydantic import BaseModel


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan: str
    status: str
    asset_limit: int
    asset_count: int = 0
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    has_billing_portal: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanResponse(BaseModel):
    key: str
    name: str
    price_monthly: int
    price_yearly: int
    asset_limit: int
    features: list[str]


class CheckoutRequest(BaseModel):
    plan: str
    billing_period: str = "monthly"  # monthly or yearly


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class UsageStatsResponse(BaseModel):
    asset_count: int
    asset_limit: int
    agent_count: int
    alert_rule_count: int
    plan: str
