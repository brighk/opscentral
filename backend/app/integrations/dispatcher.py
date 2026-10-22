import hashlib
import hmac
import json
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.models import WebhookDelivery, WebhookEndpoint


def compute_signature(secret: str, payload: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def dispatch_webhook(
    db: AsyncSession,
    tenant_id: str,
    event_type: str,
    payload: dict,
) -> int:
    """Fan-out webhook to all matching endpoints for a tenant. Returns delivery count."""
    result = await db.execute(
        select(WebhookEndpoint).where(
            WebhookEndpoint.tenant_id == tenant_id,
            WebhookEndpoint.is_active == True,  # noqa: E712
        )
    )
    endpoints = result.scalars().all()

    delivery_count = 0
    payload_json = json.dumps(payload, default=str)

    for endpoint in endpoints:
        event_types = (
            json.loads(endpoint.event_types)
            if isinstance(endpoint.event_types, str)
            else endpoint.event_types
        )
        if event_type not in event_types:
            continue

        signature = compute_signature(endpoint.secret, payload_json)
        delivery = WebhookDelivery(
            endpoint_id=endpoint.id,
            event_type=event_type,
            payload=payload_json,
        )

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    endpoint.url,
                    content=payload_json,
                    headers={
                        "Content-Type": "application/json",
                        "X-OC-Signature": signature,
                        "X-OC-Event": event_type,
                    },
                )
            duration_ms = int((time.monotonic() - start) * 1000)
            delivery.status_code = resp.status_code
            delivery.response_body = resp.text[:2000] if resp.text else None
            delivery.duration_ms = duration_ms

            endpoint.last_triggered_at = datetime.now(UTC)
            endpoint.last_status_code = resp.status_code

            if resp.status_code >= 400:
                endpoint.failure_count += 1
            else:
                endpoint.failure_count = 0

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            delivery.status_code = 0
            delivery.response_body = str(e)[:2000]
            delivery.duration_ms = duration_ms
            endpoint.failure_count += 1

        # Auto-disable after 10 consecutive failures
        if endpoint.failure_count >= 10:
            endpoint.is_active = False

        db.add(delivery)
        delivery_count += 1

    await db.commit()
    return delivery_count
