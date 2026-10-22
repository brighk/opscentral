"""Notification dispatchers for different channel types."""

import logging

import httpx

from app.notifications.models import NotificationChannel

logger = logging.getLogger(__name__)

SEVERITY_COLORS = {
    "info": "#2196F3",
    "warning": "#FF9800",
    "critical": "#F44336",
}

SEVERITY_EMOJI = {
    "info": ":information_source:",
    "warning": ":warning:",
    "critical": ":rotating_light:",
}


async def dispatch_notification(
    channel: NotificationChannel,
    title: str,
    message: str,
    severity: str = "info",
) -> bool:
    """Dispatch a notification through the given channel. Returns True on success."""
    try:
        dispatcher = DISPATCHERS.get(channel.channel_type)
        if not dispatcher:
            logger.error(f"Unknown channel type: {channel.channel_type}")
            return False
        return await dispatcher(channel.config, title, message, severity)
    except Exception as e:
        logger.error(f"Failed to dispatch notification via {channel.channel_type}: {e}")
        return False


async def _dispatch_slack(config: dict, title: str, message: str, severity: str) -> bool:
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        logger.error("Slack webhook_url not configured")
        return False

    color = SEVERITY_COLORS.get(severity, "#2196F3")
    emoji = SEVERITY_EMOJI.get(severity, "")
    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"{emoji} {title}",
                "text": message,
                "footer": "OpsCentral",
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    return True


async def _dispatch_teams(config: dict, title: str, message: str, severity: str) -> bool:
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        logger.error("Teams webhook_url not configured")
        return False

    color = SEVERITY_COLORS.get(severity, "#2196F3")
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color.lstrip("#"),
        "summary": title,
        "sections": [
            {
                "activityTitle": title,
                "text": message,
                "facts": [{"name": "Severity", "value": severity.upper()}],
            }
        ],
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    return True


async def _dispatch_discord(config: dict, title: str, message: str, severity: str) -> bool:
    webhook_url = config.get("webhook_url")
    if not webhook_url:
        logger.error("Discord webhook_url not configured")
        return False

    color_hex = SEVERITY_COLORS.get(severity, "#2196F3")
    # Discord expects color as int
    color_int = int(color_hex.lstrip("#"), 16)
    payload = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": color_int,
                "footer": {"text": "OpsCentral"},
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
    return True


async def _dispatch_webhook(config: dict, title: str, message: str, severity: str) -> bool:
    url = config.get("url")
    if not url:
        logger.error("Webhook URL not configured")
        return False

    method = config.get("method", "POST").upper()
    headers = config.get("headers", {})
    headers.setdefault("Content-Type", "application/json")

    payload = {
        "title": title,
        "message": message,
        "severity": severity,
        "source": "OpsCentral",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.request(method, url, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
    return True


async def _dispatch_email(config: dict, title: str, message: str, severity: str) -> bool:
    recipients = config.get("recipients", [])
    if not recipients:
        logger.error("No email recipients configured")
        return False

    from app.notifications.service import send_alert_email

    for email in recipients:
        await send_alert_email(email, title, message, severity)
    return True


DISPATCHERS = {
    "slack": _dispatch_slack,
    "teams": _dispatch_teams,
    "discord": _dispatch_discord,
    "webhook": _dispatch_webhook,
    "email": _dispatch_email,
}
