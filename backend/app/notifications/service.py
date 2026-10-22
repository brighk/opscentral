import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.config import settings

logger = logging.getLogger(__name__)

template_dir = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))


async def send_alert_email(to_email: str, alert_title: str, alert_message: str, severity: str):
    """Send alert notification email."""
    if not settings.SMTP_USER:
        logger.warning("SMTP not configured, skipping email notification")
        return

    try:
        from emails.message import Message

        template = jinja_env.get_template("alert_notification.html")
        html = template.render(
            title=alert_title,
            message=alert_message,
            severity=severity,
            app_name=settings.APP_NAME,
        )

        msg = Message(
            subject=f"[{settings.APP_NAME}] {severity.upper()}: {alert_title}",
            html=html,
            mail_from=(settings.APP_NAME, settings.EMAIL_FROM),
        )

        msg.send(
            to=to_email,
            smtp={
                "host": settings.SMTP_HOST,
                "port": settings.SMTP_PORT,
                "user": settings.SMTP_USER,
                "password": settings.SMTP_PASSWORD,
                "tls": True,
            },
        )
        logger.info(f"Alert email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
