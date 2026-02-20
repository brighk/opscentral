import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Import all models
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

TEST_DB_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
