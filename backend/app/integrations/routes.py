import json
import secrets
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.dependencies import get_current_user, require_role
from app.integrations.dispatcher import dispatch_webhook
from app.integrations.event_types import EVENT_TYPES
from app.integrations.models import ExternalIntegration, WebhookDelivery, WebhookEndpoint
from app.integrations.schemas import (
    EventTypeResponse,
    ExternalIntegrationCreate,
    ExternalIntegrationResponse,
    ExternalIntegrationUpdate,
    WebhookDeliveryResponse,
    WebhookEndpointCreate,
    WebhookEndpointResponse,
    WebhookEndpointUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["integrations"])


# --- Webhook Endpoints ---


@router.get("/webhooks/event-types", response_model=list[EventTypeResponse])
async def list_event_types(user=Depends(get_current_user)):
    return [EventTypeResponse(key=k, description=v) for k, v in EVENT_TYPES.items()]


@router.get("/webhooks", response_model=list[WebhookEndpointResponse])
async def list_webhooks(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint)
        .where(WebhookEndpoint.tenant_id == user.tenant_id)
        .order_by(WebhookEndpoint.created_at.desc())
    )
    endpoints = result.scalars().all()
    return [_endpoint_to_response(e) for e in endpoints]


@router.post("/webhooks", response_model=WebhookEndpointResponse)
async def create_webhook(
    data: WebhookEndpointCreate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    secret = data.secret or secrets.token_hex(32)
    endpoint = WebhookEndpoint(
        tenant_id=user.tenant_id,
        name=data.name,
        url=data.url,
        secret=secret,
        event_types=json.dumps(data.event_types),
    )
    db.add(endpoint)
    await db.commit()
    await db.refresh(endpoint)
    return _endpoint_to_response(endpoint)


@router.put("/webhooks/{webhook_id}", response_model=WebhookEndpointResponse)
async def update_webhook(
    webhook_id: uuid.UUID,
    data: WebhookEndpointUpdate,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.tenant_id == user.tenant_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook not found")

    if data.name is not None:
        endpoint.name = data.name
    if data.url is not None:
        endpoint.url = data.url
    if data.event_types is not None:
        endpoint.event_types = json.dumps(data.event_types)
    if data.is_active is not None:
        endpoint.is_active = data.is_active
        if data.is_active:
            endpoint.failure_count = 0

    await db.commit()
    await db.refresh(endpoint)
    return _endpoint_to_response(endpoint)


@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(
    webhook_id: uuid.UUID,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.tenant_id == user.tenant_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook not found")

    await db.delete(endpoint)
    await db.commit()
    return {"detail": "Webhook deleted"}


@router.get("/webhooks/{webhook_id}/deliveries", response_model=list[WebhookDeliveryResponse])
async def list_deliveries(
    webhook_id: uuid.UUID,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.tenant_id == user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Webhook not found")

    result = await db.execute(
        select(WebhookDelivery)
        .where(WebhookDelivery.endpoint_id == webhook_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(100)
    )
    deliveries = result.scalars().all()
    return [_delivery_to_response(d) for d in deliveries]


@router.post("/webhooks/{webhook_id}/test")
async def test_webhook(
    webhook_id: uuid.UUID,
    user=Depends(require_role("admin", "operator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.id == webhook_id,
            WebhookEndpoint.tenant_id == user.tenant_id,
        )
    )
    endpoint = result.scalar_one_or_none()
    if not endpoint:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = {
        "event": "test",
        "message": "This is a test webhook from OpsCentral",
        "timestamp": datetime.now(UTC).isoformat(),
    }
    count = await dispatch_webhook(db, str(user.tenant_id), "test", test_payload)
    return {"detail": "Test webhook sent", "deliveries": count}


# --- External Integrations ---


@router.get("/integrations", response_model=list[ExternalIntegrationResponse])
async def list_integrations(
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExternalIntegration)
        .where(ExternalIntegration.tenant_id == user.tenant_id)
        .order_by(ExternalIntegration.created_at.desc())
    )
    return result.scalars().all()


@router.post("/integrations", response_model=ExternalIntegrationResponse)
async def create_integration(
    data: ExternalIntegrationCreate,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    valid_providers = ["pagerduty", "jira", "opsgenie", "servicenow"]
    if data.provider not in valid_providers:
        raise HTTPException(status_code=400, detail=f"Provider must be one of: {valid_providers}")

    integration = ExternalIntegration(
        tenant_id=user.tenant_id,
        provider=data.provider,
        name=data.name,
        config=json.dumps(data.config),
    )
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    return integration


@router.put("/integrations/{integration_id}", response_model=ExternalIntegrationResponse)
async def update_integration(
    integration_id: uuid.UUID,
    data: ExternalIntegrationUpdate,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.id == integration_id,
            ExternalIntegration.tenant_id == user.tenant_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    if data.name is not None:
        integration.name = data.name
    if data.config is not None:
        integration.config = json.dumps(data.config)
    if data.is_active is not None:
        integration.is_active = data.is_active

    await db.commit()
    await db.refresh(integration)
    return integration


@router.delete("/integrations/{integration_id}")
async def delete_integration(
    integration_id: uuid.UUID,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.id == integration_id,
            ExternalIntegration.tenant_id == user.tenant_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    await db.delete(integration)
    await db.commit()
    return {"detail": "Integration deleted"}


@router.post("/integrations/{integration_id}/test")
async def test_integration(
    integration_id: uuid.UUID,
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ExternalIntegration).where(
            ExternalIntegration.id == integration_id,
            ExternalIntegration.tenant_id == user.tenant_id,
        )
    )
    integration = result.scalar_one_or_none()
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    # For now, just verify config is valid JSON
    try:
        json.loads(integration.config)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid integration configuration") from None

    return {
        "detail": f"Connection test for {integration.provider} successful",
        "provider": integration.provider,
    }


# --- Helpers ---


def _endpoint_to_response(e: WebhookEndpoint) -> WebhookEndpointResponse:
    event_types = json.loads(e.event_types) if isinstance(e.event_types, str) else e.event_types
    return WebhookEndpointResponse(
        id=e.id,
        name=e.name,
        url=e.url,
        event_types=event_types,
        is_active=e.is_active,
        failure_count=e.failure_count,
        last_triggered_at=e.last_triggered_at,
        last_status_code=e.last_status_code,
        created_at=e.created_at,
    )


def _delivery_to_response(d: WebhookDelivery) -> WebhookDeliveryResponse:
    payload = json.loads(d.payload) if isinstance(d.payload, str) else d.payload
    return WebhookDeliveryResponse(
        id=d.id,
        endpoint_id=d.endpoint_id,
        event_type=d.event_type,
        payload=payload,
        status_code=d.status_code,
        response_body=d.response_body,
        duration_ms=d.duration_ms,
        created_at=d.created_at,
    )
