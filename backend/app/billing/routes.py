from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.plans import PLAN_TIERS
from app.billing.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PlanResponse,
    PortalResponse,
    SubscriptionResponse,
    UsageStatsResponse,
)
from app.billing.service import (
    create_checkout_session,
    create_customer_portal_session,
    get_or_create_subscription,
    get_usage_stats,
    handle_webhook_event,
)
from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.exceptions import BadRequestError

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sub = await get_or_create_subscription(user.tenant_id, db)
    stats = await get_usage_stats(user.tenant_id, db)
    return SubscriptionResponse(
        id=sub.id,
        plan=sub.plan,
        status=sub.status,
        asset_limit=sub.asset_limit,
        asset_count=stats["asset_count"],
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        created_at=sub.created_at,
    )


@router.get("/plans", response_model=list[PlanResponse])
async def list_plans():
    return [
        PlanResponse(
            key=key,
            name=tier["name"],
            price_monthly=tier["price_monthly"],
            price_yearly=tier["price_yearly"],
            asset_limit=tier["asset_limit"],
            features=tier["features"],
        )
        for key, tier in PLAN_TIERS.items()
    ]


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    sub = await get_or_create_subscription(user.tenant_id, db)
    url = create_checkout_session(
        tenant_id=user.tenant_id,
        plan=body.plan,
        billing_period=body.billing_period,
        customer_id=sub.stripe_customer_id,
    )
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    sub = await get_or_create_subscription(user.tenant_id, db)
    if not sub.stripe_customer_id:
        raise BadRequestError("No active Stripe subscription")
    url = create_customer_portal_session(sub.stripe_customer_id)
    return PortalResponse(portal_url=url)


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    payload = await request.body()
    await handle_webhook_event(payload, stripe_signature, db)
    return {"status": "ok"}


@router.get("/usage", response_model=UsageStatsResponse)
async def usage_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await get_usage_stats(user.tenant_id, db)
    return UsageStatsResponse(**stats)
