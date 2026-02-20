# Server Guide

The OpsCentral server is the central hub. It runs the API, stores all data, evaluates alerts, and serves the web dashboard. You run one server; all agents report to it.

## What the Server Does

1. **Receives data** from agents (metrics, heartbeats, inventory) via REST API
2. **Stores everything** in PostgreSQL (TimescaleDB for time-series metrics)
3. **Evaluates alert rules** every 60 seconds via Celery background workers
4. **Sends notifications** (email) when alerts fire or resolve
5. **Serves the dashboard** — a React web app that shows all your data
6. **Pushes real-time updates** to open dashboards via WebSocket + Redis pub/sub

## Components

```
┌─────────────────────────────────────────────────────────────┐
│  OpsCentral Server                                          │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ React    │  │ FastAPI      │  │ Celery Workers     │    │
│  │ Frontend │→ │ Backend      │← │ (alert evaluation, │    │
│  │ :5173    │  │ :8000        │  │  notifications)    │    │
│  └──────────┘  └──────┬───────┘  └────────┬───────────┘    │
│                       │                    │                │
│              ┌────────┴────────┐  ┌───────┴──────┐         │
│              │ PostgreSQL      │  │ Redis        │         │
│              │ (TimescaleDB)   │  │ (cache,      │         │
│              │ :5432           │  │  pub/sub,    │         │
│              │                 │  │  Celery      │         │
│              │ - Users/Tenants │  │  broker)     │         │
│              │ - Agents        │  │ :6379        │         │
│              │ - Metrics       │  └──────────────┘         │
│              │ - Assets        │                            │
│              │ - Alerts        │                            │
│              └─────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

All settings are controlled via environment variables with the `OC_` prefix. Create a `.env` file in the backend directory or export them in your shell.

### Required Settings

| Variable | Default | Description |
|---|---|---|
| `OC_DATABASE_URL` | `postgresql+asyncpg://opscentral:opscentral_dev@localhost:5432/opscentral` | PostgreSQL connection string |
| `OC_REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `OC_SECRET_KEY` | `change-me-in-production...` | JWT signing key. **Generate a real one for production**: `openssl rand -hex 32` |

### Authentication Settings

| Variable | Default | Description |
|---|---|---|
| `OC_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | How long access tokens are valid |
| `OC_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | How long refresh tokens are valid |
| `OC_ALGORITHM` | `HS256` | JWT algorithm |

### Email / SMTP Settings

| Variable | Default | Description |
|---|---|---|
| `OC_SMTP_HOST` | `smtp.gmail.com` | SMTP server hostname |
| `OC_SMTP_PORT` | `587` | SMTP port (587 for TLS) |
| `OC_SMTP_USER` | (empty) | SMTP username. If empty, email notifications are disabled. |
| `OC_SMTP_PASSWORD` | (empty) | SMTP password or app-specific password |
| `OC_EMAIL_FROM` | `noreply@opscentral.io` | Sender address for notification emails |

### Application Settings

| Variable | Default | Description |
|---|---|---|
| `OC_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins (JSON array) |
| `OC_DEBUG` | `true` | Enable debug mode (SQL logging, etc.) Set to `false` in production. |
| `OC_APP_NAME` | `OpsCentral` | Application name shown in UI and emails |

### Production Example

```bash
# .env file for production
OC_DATABASE_URL=postgresql+asyncpg://opscentral:STRONG_PASSWORD@db.internal:5432/opscentral
OC_REDIS_URL=redis://redis.internal:6379/0
OC_SECRET_KEY=a1b2c3d4e5f6...your-64-char-hex-key...
OC_CORS_ORIGINS=["https://ops.yourcompany.com"]
OC_DEBUG=false
OC_SMTP_HOST=smtp.gmail.com
OC_SMTP_PORT=587
OC_SMTP_USER=alerts@yourcompany.com
OC_SMTP_PASSWORD=your-app-password
OC_EMAIL_FROM=alerts@yourcompany.com
```

## Database Migrations

The database schema is managed by Alembic. Migrations run automatically but you can also run them manually:

```bash
# Apply all pending migrations
cd backend
alembic upgrade head

# Create a new migration after model changes
alembic revision --autogenerate -m "add new column"

# Check current migration status
alembic current
```

## Multi-Tenancy

OpsCentral supports multiple tenants (organizations) in a single server instance. Each tenant:

- Has their own users, agents, assets, and alerts
- Cannot see other tenants' data
- Is identified by a `tenant_id` UUID attached to every record

When a user registers, a new tenant is automatically created. Additional users can be added to the same tenant (the user management API can be extended for this).

### Pricing Tiers

The `Tenant` model includes `plan` and `max_assets` fields for enforcing tiers:

| Plan | Max Assets | Intended Price |
|---|---|---|
| `starter` | 25 | $99/mo |
| `professional` | 100 | $249/mo |
| `business` | 250 | $499/mo |
| `enterprise` | unlimited | Custom |

Tier enforcement is not yet implemented in the API but the data model supports it.

## Running in Production

### With Systemd

Create `/etc/systemd/system/opscentral-api.service`:

```ini
[Unit]
Description=OpsCentral API
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=opscentral
WorkingDirectory=/opt/opscentral/backend
ExecStart=/opt/opscentral/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5
EnvironmentFile=/opt/opscentral/.env

[Install]
WantedBy=multi-user.target
```

Create similar service files for Celery worker and Celery beat.

### With a Reverse Proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name ops.yourcompany.com;

    ssl_certificate /etc/letsencrypt/live/ops.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ops.yourcompany.com/privkey.pem;

    # Frontend (static build)
    location / {
        root /opt/opscentral/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Build the frontend for production:

```bash
cd frontend
npm run build
# Output is in frontend/dist/
```

## Monitoring the Server Itself

You can install the OpsCentral agent on the server machine itself to monitor its own health. This gives you CPU/memory/disk metrics for the server and alerts if the server itself is under stress.

## Backup

Back up the PostgreSQL database regularly:

```bash
pg_dump -U opscentral -h localhost opscentral > backup_$(date +%Y%m%d).sql
```

Redis data is ephemeral (cache, pub/sub messages) and does not need to be backed up.
