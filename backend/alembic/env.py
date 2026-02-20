from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.db.base import Base

# Import all models so they register with Base.metadata
from app.auth.models import Tenant, User  # noqa: F401
from app.agents.models import Agent  # noqa: F401
from app.monitoring.models import Metric  # noqa: F401
from app.assets.models import Asset, SoftwareInventory  # noqa: F401
from app.alerting.models import AlertRule, Alert  # noqa: F401
from app.monitoring.process_models import ProcessSnapshot  # noqa: F401
from app.notifications.models import NotificationChannel  # noqa: F401
from app.healthchecks.models import HealthCheck, HealthCheckLog  # noqa: F401
from app.agents.status_models import AgentStatusLog  # noqa: F401
from app.vulnerabilities.models import Vulnerability, VulnerabilityScan  # noqa: F401
from app.auth.audit_models import AuditLog  # noqa: F401
from app.dashboards.models import CustomDashboard, DashboardWidget  # noqa: F401
from app.api_keys.models import APIKey  # noqa: F401
from app.billing.models import Subscription, BillingEvent  # noqa: F401
from app.reports.models import Report, ReportSchedule, ComplianceScore  # noqa: F401
from app.remote_actions.models import RemoteAction  # noqa: F401
from app.integrations.models import WebhookEndpoint, WebhookDelivery, ExternalIntegration  # noqa: F401
from app.runbooks.models import Runbook, RunbookExecution, RunbookStepExecution  # noqa: F401
from app.incidents.models import Incident, IncidentUpdate, IncidentTag, Postmortem  # noqa: F401
from app.oncall.models import OnCallSchedule, OnCallOverride, EscalationPolicy  # noqa: F401
from app.maintenance.models import MaintenanceWindow  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override URL from settings
sync_url = settings.DATABASE_URL.replace("+asyncpg", "")
config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
