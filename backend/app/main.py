from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.middleware import RequestTimingMiddleware, SecurityHeadersMiddleware
from app.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    from app.db.session import engine

    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="All-in-one IT Operations Platform for SMBs",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    # slowapi's handler is typed for RateLimitExceeded, narrower than Starlette expects
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # pyright: ignore[reportArgumentType]

    # Global 500 handler
    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestTimingMiddleware)

    # Register routers
    from app.agents.routes import gateway as gateway_router
    from app.agents.routes import router as agents_router
    from app.alerting.routes import router as alerting_router
    from app.api_keys.routes import router as api_keys_router
    from app.assets.routes import router as assets_router
    from app.auth.routes import router as auth_router
    from app.billing.routes import router as billing_router
    from app.dashboard.routes import router as dashboard_router
    from app.dashboards.routes import router as custom_dashboards_router
    from app.healthchecks.routes import router as healthchecks_router
    from app.incidents.routes import router as incidents_router
    from app.integrations.routes import router as integrations_router
    from app.maintenance.routes import router as maintenance_router
    from app.monitoring.routes import router as monitoring_router
    from app.notifications.routes import router as notifications_router
    from app.oncall.routes import router as oncall_router
    from app.remote_actions.routes import router as remote_actions_router
    from app.reports.routes import router as reports_router
    from app.runbooks.routes import router as runbooks_router
    from app.uptime.routes import public_router as status_page_router
    from app.uptime.routes import router as uptime_router
    from app.vulnerabilities.routes import router as vulnerabilities_router

    app.include_router(auth_router)
    app.include_router(agents_router)
    app.include_router(gateway_router)
    app.include_router(monitoring_router)
    app.include_router(assets_router)
    app.include_router(alerting_router)
    app.include_router(dashboard_router)
    app.include_router(notifications_router)
    app.include_router(healthchecks_router)
    app.include_router(vulnerabilities_router)
    app.include_router(custom_dashboards_router)
    app.include_router(uptime_router)
    app.include_router(status_page_router)
    app.include_router(api_keys_router)
    app.include_router(billing_router)
    app.include_router(reports_router)
    app.include_router(remote_actions_router)
    app.include_router(integrations_router)
    app.include_router(runbooks_router)
    app.include_router(incidents_router)
    app.include_router(oncall_router)
    app.include_router(maintenance_router)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": settings.APP_NAME}

    return app


app = create_app()
