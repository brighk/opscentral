import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.models import BillingEvent, Subscription
from app.billing.plans import PLAN_TIERS
from app.config import settings
from app.exceptions import BadRequestError, PaymentRequiredError


async def get_or_create_subscription(tenant_id: uuid.UUID, db: AsyncSession) -> Subscription:
    result = await db.execute(
        select(Subscription).where(Subscription.tenant_id == tenant_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        sub = Subscription(tenant_id=tenant_id, plan="free", status="active", asset_limit=5)
        db.add(sub)
        await db.flush()
    return sub


async def get_usage_stats(tenant_id: uuid.UUID, db: AsyncSession) -> dict:
    from app.agents.models import Agent
    from app.alerting.models import AlertRule
    from app.assets.models import Asset

    sub = await get_or_create_subscription(tenant_id, db)

    asset_count_result = await db.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id)
    )
    asset_count = asset_count_result.scalar() or 0

    agent_count_result = await db.execute(
        select(func.count())
        .select_from(Agent)
        .where(Agent.tenant_id == tenant_id, Agent.is_active == True)  # noqa: E712
    )
    agent_count = agent_count_result.scalar() or 0

    rule_count_result = await db.execute(
        select(func.count())
        .select_from(AlertRule)
        .where(AlertRule.tenant_id == tenant_id, AlertRule.is_enabled == True)  # noqa: E712
    )
    rule_count = rule_count_result.scalar() or 0

    return {
        "asset_count": asset_count,
        "asset_limit": sub.asset_limit,
        "agent_count": agent_count,
        "alert_rule_count": rule_count,
        "plan": sub.plan,
    }


async def enforce_asset_limit(tenant_id: uuid.UUID, db: AsyncSession):
    from app.assets.models import Asset

    sub = await get_or_create_subscription(tenant_id, db)

    asset_count_result = await db.execute(
        select(func.count()).select_from(Asset).where(Asset.tenant_id == tenant_id)
    )
    asset_count = asset_count_result.scalar() or 0

    if asset_count >= sub.asset_limit:
        raise PaymentRequiredError(
            f"Asset limit reached ({sub.asset_limit}). Upgrade your plan to add more assets."
        )


def create_checkout_session(
    tenant_id: uuid.UUID,
    plan: str,
    billing_period: str,
    customer_id: str | None,
) -> str:
    if plan not in PLAN_TIERS or plan == "free":
        raise BadRequestError("Invalid plan")

    tier = PLAN_TIERS[plan]
    price_key = f"stripe_price_id_{billing_period}"
    price_id = tier.get(price_key)

    if not settings.STRIPE_SECRET_KEY:
        raise BadRequestError("Stripe is not configured")

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY

    session_params = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"{settings.FRONTEND_URL}/billing?success=true",
        "cancel_url": f"{settings.FRONTEND_URL}/billing?canceled=true",
        "metadata": {"tenant_id": str(tenant_id), "plan": plan},
    }
    if customer_id:
        session_params["customer"] = customer_id

    session = stripe.checkout.Session.create(**session_params)
    return session.url


def create_customer_portal_session(customer_id: str) -> str:
    if not settings.STRIPE_SECRET_KEY:
        raise BadRequestError("Stripe is not configured")

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{settings.FRONTEND_URL}/billing",
    )
    return session.url


async def handle_webhook_event(payload: bytes, sig_header: str, db: AsyncSession):
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BadRequestError("Webhook secret not configured")

    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY

    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
    )

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        tenant_id = uuid.UUID(data["metadata"]["tenant_id"])
        plan = data["metadata"]["plan"]
        customer_id = data["customer"]
        subscription_id = data["subscription"]

        sub = await get_or_create_subscription(tenant_id, db)
        sub.stripe_customer_id = customer_id
        sub.stripe_subscription_id = subscription_id
        sub.plan = plan
        sub.asset_limit = PLAN_TIERS[plan]["asset_limit"]
        sub.status = "active"

    elif event_type == "customer.subscription.updated":
        subscription_id = data["id"]
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = data["status"]

    elif event_type == "customer.subscription.deleted":
        subscription_id = data["id"]
        result = await db.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == subscription_id
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.status = "canceled"
            sub.plan = "free"
            sub.asset_limit = PLAN_TIERS["free"]["asset_limit"]

    # Log the event
    billing_event = BillingEvent(
        tenant_id=sub.tenant_id if "sub" in dir() else uuid.UUID("00000000-0000-0000-0000-000000000000"),
        event_type=event_type,
        stripe_event_id=event["id"],
        data={"object_id": data.get("id")},
    )
    db.add(billing_event)
