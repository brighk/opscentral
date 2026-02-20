# Architecture

## Design Philosophy

OpsCentral is built as a **modular monolith** — all backend code runs in a single FastAPI process, but each domain (auth, agents, monitoring, assets, alerting) is a separate Python package with its own models, routes, and schemas. This keeps things simple for a small team while maintaining clean boundaries that could be split into services later if needed.

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  CLIENT TIER                                                        │
│                                                                     │
│  ┌───────────────────┐    ┌───────────────────────────────────────┐ │
│  │  React SPA        │    │  OpsCentral Agents                   │ │
│  │  (Vite + Mantine) │    │  (Python + psutil)                   │ │
│  │                   │    │                                       │ │
│  │  - Dashboard      │    │  One per monitored machine:           │ │
│  │  - Monitoring     │    │  - Linux (any distro)                │ │
│  │  - Assets         │    │  - Windows                           │ │
│  │  - Alerts         │    │  - macOS                             │ │
│  │  - Agents         │    │                                       │ │
│  └────────┬──────────┘    └─────────────────┬─────────────────────┘ │
│           │ HTTP + WebSocket                 │ HTTP                  │
└───────────┼──────────────────────────────────┼──────────────────────┘
            │                                  │
┌───────────┼──────────────────────────────────┼──────────────────────┐
│  API TIER │                                  │                      │
│           ▼                                  ▼                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  FastAPI Application                                         │   │
│  │                                                              │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐ │   │
│  │  │ Auth     │ │ Agents   │ │ Monitoring │ │ Assets       │ │   │
│  │  │ Module   │ │ Module   │ │ Module     │ │ Module       │ │   │
│  │  │          │ │          │ │            │ │              │ │   │
│  │  │ register │ │ register │ │ query      │ │ list         │ │   │
│  │  │ login    │ │ gateway  │ │ metrics    │ │ detail       │ │   │
│  │  │ refresh  │ │ heartbeat│ │ status     │ │ software     │ │   │
│  │  │ me       │ │ metrics  │ │ overview   │ │ auto-create  │ │   │
│  │  └──────────┘ │ inventory│ └────────────┘ └──────────────┘ │   │
│  │               └──────────┘                                  │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐                  │   │
│  │  │ Alerting │ │ Dashboard│ │ Notifs     │                  │   │
│  │  │ Module   │ │ Module   │ │ Module     │                  │   │
│  │  │          │ │          │ │            │                  │   │
│  │  │ rules    │ │ WebSocket│ │ email      │                  │   │
│  │  │ alerts   │ │ pub/sub  │ │ templates  │                  │   │
│  │  │ ack/     │ │          │ │            │                  │   │
│  │  │ resolve  │ │          │ │            │                  │   │
│  │  └──────────┘ └──────────┘ └────────────┘                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Celery Workers                                              │   │
│  │                                                              │   │
│  │  Beat Schedule:                                              │   │
│  │  - evaluate_alert_rules  (every 60s)                        │   │
│  │  - detect_stale_agents   (every 120s)                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
            │                          │
┌───────────┼──────────────────────────┼──────────────────────────────┐
│  DATA TIER│                          │                              │
│           ▼                          ▼                              │
│  ┌─────────────────────┐    ┌─────────────────────┐                │
│  │ PostgreSQL 16       │    │ Redis 7             │                │
│  │ (TimescaleDB)       │    │                     │                │
│  │                     │    │ - Celery broker     │                │
│  │ Tables:             │    │ - Pub/sub channels  │                │
│  │ - tenants           │    │   (dashboard:{id})  │                │
│  │ - users             │    │ - Result backend    │                │
│  │ - agents            │    │                     │                │
│  │ - metrics           │    │                     │                │
│  │ - assets            │    │                     │                │
│  │ - software_inventory│    │                     │                │
│  │ - alert_rules       │    │                     │                │
│  │ - alerts            │    │                     │                │
│  └─────────────────────┘    └─────────────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Agent → Server → Dashboard

1. Agent collects CPU/memory/disk/network metrics using `psutil`
2. Agent POSTs metrics to `POST /api/v1/gateway/metrics` with its API key
3. FastAPI validates the API key, writes metrics to PostgreSQL
4. FastAPI publishes a message to Redis channel `dashboard:{tenant_id}`
5. The WebSocket endpoint listening on that channel pushes the update to any connected dashboards
6. React dashboard receives the WebSocket message and refetches data via TanStack Query

### Alert Evaluation

1. Celery beat triggers `evaluate_alert_rules` every 60 seconds
2. Worker loads all enabled `AlertRule` records
3. For each rule, queries recent metrics (over the rule's `duration_seconds` window)
4. Computes the average metric value and checks against the threshold
5. If condition is met and no existing firing alert: creates a new `Alert` record and sends email
6. If condition is no longer met and an alert exists: auto-resolves it

### Asset Auto-Discovery

1. Agent sends inventory to `POST /api/v1/gateway/inventory`
2. Server looks up an existing `Asset` by `agent_id`
3. If found: updates hardware info and replaces software list
4. If not found: creates a new `Asset` record and populates software
5. Asset appears immediately in the dashboard's Assets page

## Authentication

Two separate auth mechanisms:

### User Auth (JWT)

- Users authenticate with email/password
- Server returns an access token (15 min TTL) and refresh token (7 day TTL)
- Access tokens are sent as `Authorization: Bearer <token>` headers
- Refresh tokens are used to get new access/refresh pairs without re-login
- All user-facing endpoints require a valid access token

### Agent Auth (API Key)

- Each agent has a unique 64-character hex API key generated at registration
- Agents send their key as `X-Agent-Key: <key>` header
- Gateway endpoints validate the key and extract the `agent_id` and `tenant_id`
- API keys are tied to a tenant, so agents can only write to their tenant's data

## Database Schema

### Core Tables

```
tenants
├── id (UUID, PK)
├── name
├── slug (unique)
├── plan (starter/professional/business/enterprise)
├── max_assets
├── is_active
├── created_at, updated_at

users
├── id (UUID, PK)
├── tenant_id (FK → tenants)
├── email (unique)
├── hashed_password (bcrypt)
├── full_name
├── is_active, is_admin
├── created_at, updated_at

agents
├── id (UUID, PK)
├── tenant_id (FK → tenants)
├── hostname, display_name
├── api_key (unique, 64-char hex)
├── os_type, os_version, agent_version
├── ip_address, last_seen
├── is_active, metadata
├── created_at, updated_at
```

### Monitoring Tables

```
metrics
├── id (serial, PK)
├── tenant_id (UUID)
├── agent_id (FK → agents)
├── metric_name, metric_value, unit
├── tags (JSON)
├── recorded_at (timestamptz, indexed)

assets
├── id (UUID, PK)
├── tenant_id (UUID)
├── agent_id (FK → agents, unique)
├── hostname, asset_type, status
├── os_type, os_version
├── cpu_model, cpu_cores, ram_total_gb, disk_total_gb
├── ip_addresses, mac_addresses (JSON)
├── system_info (JSON)
├── created_at, updated_at

software_inventory
├── id (UUID, PK)
├── asset_id (FK → assets)
├── name, version, publisher
├── created_at, updated_at
```

### Alerting Tables

```
alert_rules
├── id (UUID, PK)
├── tenant_id (UUID)
├── name, description
├── metric_name, condition (gt/lt/gte/lte/eq), threshold
├── duration_seconds
├── agent_id (optional — rule for specific agent or all)
├── severity (info/warning/critical)
├── is_enabled, notify_email
├── created_at, updated_at

alerts
├── id (UUID, PK)
├── tenant_id (UUID)
├── rule_id (FK → alert_rules, nullable for system alerts)
├── agent_id (optional)
├── status (firing/acknowledged/resolved)
├── severity, title, message
├── metric_value
├── fired_at, resolved_at
├── acknowledged_at, acknowledged_by
├── created_at, updated_at
```

## Technology Choices

| Component | Technology | Why |
|---|---|---|
| Backend framework | FastAPI | Async, auto-generated API docs, type-safe with Pydantic |
| ORM | SQLAlchemy 2.0 (async) | Industry standard, excellent migration support via Alembic |
| Database | PostgreSQL 16 (TimescaleDB) | Relational data + time-series metrics in one database |
| Cache/Broker | Redis 7 | Fast pub/sub for real-time dashboard, Celery task broker |
| Task queue | Celery 5.4 | Reliable background task execution on a schedule |
| Agent metrics | psutil | Cross-platform system metrics library |
| Frontend | React 19 + TypeScript | Component-based UI with type safety |
| UI library | Mantine v8 | Clean, modern components with good defaults |
| Charts | Recharts | Simple declarative charts built on D3 |
| State | Zustand + TanStack Query | Minimal client state (Zustand), server state caching (TanStack) |
| Forms | React Hook Form + Zod | Performant forms with schema validation |
