from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "OC_"}

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://opscentral:opscentral_dev@localhost:5432/opscentral"
    DATABASE_URL_SYNC: str = "postgresql://opscentral:opscentral_dev@localhost:5432/opscentral"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@opscentral.io"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Webhooks
    WEBHOOK_TIMEOUT_SECONDS: int = 10
    WEBHOOK_MAX_RETRIES: int = 3
    PAGERDUTY_ROUTING_KEY: str = ""

    # Outbound requests to user-supplied URLs (runbook webhooks, Jira, ServiceNow)
    # are limited to public addresses. Self-hosted installs that need to reach
    # internal systems can allow private/loopback targets.
    ALLOW_PRIVATE_NETWORK_TARGETS: bool = False

    # App
    APP_NAME: str = "OpsCentral"
    DEBUG: bool = True


settings = Settings()
