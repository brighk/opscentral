from celery import Celery
from celery.schedules import crontab  # noqa: F401

from app.config import settings

celery = Celery(
    "opscentral",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "evaluate-alert-rules": {
            "task": "app.tasks.alert_tasks.evaluate_alert_rules",
            "schedule": 60.0,
        },
        "detect-stale-agents": {
            "task": "app.tasks.alert_tasks.detect_stale_agents",
            "schedule": 120.0,
        },
        "run-health-checks": {
            "task": "app.tasks.healthcheck_tasks.run_health_checks",
            "schedule": 30.0,
        },
        "cleanup-old-metrics": {
            "task": "app.tasks.retention_tasks.cleanup_old_metrics",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        "cleanup-old-process-snapshots": {
            "task": "app.tasks.retention_tasks.cleanup_old_process_snapshots",
            "schedule": crontab(hour=2, minute=15),  # Daily at 2:15 AM
        },
        "cleanup-old-healthcheck-logs": {
            "task": "app.tasks.retention_tasks.cleanup_old_healthcheck_logs",
            "schedule": crontab(hour=2, minute=30),  # Daily at 2:30 AM
        },
        "scan-vulnerabilities": {
            "task": "app.tasks.vuln_tasks.scan_all_assets",
            "schedule": crontab(hour="*/6", minute=0),  # Every 6 hours
        },
        "run-scheduled-reports": {
            "task": "app.tasks.report_tasks.run_scheduled_reports",
            "schedule": crontab(minute=0),  # Every hour
        },
        "calculate-compliance-scores": {
            "task": "app.tasks.report_tasks.calculate_compliance_scores",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        },
        "expire-stale-actions": {
            "task": "app.tasks.action_tasks.expire_stale_actions",
            "schedule": 60.0,  # Every 60 seconds
        },
        "cleanup-webhook-deliveries": {
            "task": "app.tasks.webhook_tasks.cleanup_old_deliveries",
            "schedule": crontab(hour=4, minute=0),  # Daily at 4 AM
        },
        "run-escalations": {
            "task": "app.tasks.oncall_tasks.run_escalations",
            "schedule": 60.0,  # Every 60 seconds
        },
        "send-handoff-notifications": {
            "task": "app.tasks.oncall_tasks.send_handoff_notifications",
            "schedule": crontab(minute=0),  # Every hour
        },
    },
)

# Import tasks so they are registered
celery.autodiscover_tasks(["app.tasks"])
