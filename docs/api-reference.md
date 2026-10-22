# API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (Swagger UI)

## Authentication

### Register

```
POST /api/v1/auth/register
```

Creates a new tenant and admin user. Returns JWT tokens.

**Body:**
```json
{
  "email": "admin@company.com",
  "password": "securepassword",
  "full_name": "John Doe",
  "company_name": "Acme Corp"
}
```

**Response:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Login

```
POST /api/v1/auth/login
```

**Body:**
```json
{
  "email": "admin@company.com",
  "password": "securepassword"
}
```

**Response:** Same as Register.

### Refresh Token

```
POST /api/v1/auth/refresh
```

**Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response:** New access + refresh token pair.

### Get Current User

```
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "id": "uuid",
  "email": "admin@company.com",
  "full_name": "John Doe",
  "is_admin": true,
  "tenant_id": "uuid",
  "tenant_name": "Acme Corp"
}
```

---

## Agents (User-facing)

All endpoints require `Authorization: Bearer <token>`.

### List Agents

```
GET /api/v1/agents
```

Returns all agents for the current tenant.

### Register Agent

```
POST /api/v1/agents/register
```

**Body:**
```json
{
  "hostname": "web-server-01",
  "display_name": "Production Web Server",
  "os_type": "linux",
  "os_version": "Ubuntu 22.04"
}
```

**Response:**
```json
{
  "agent_id": "uuid",
  "api_key": "64-character-hex-string"
}
```

### Deactivate Agent

```
DELETE /api/v1/agents/{agent_id}
```

---

## Agent Gateway

These endpoints are used by the agent. They require `X-Agent-Key: <api_key>` header instead of a JWT.

### Heartbeat

```
POST /api/v1/gateway/heartbeat
X-Agent-Key: <api_key>
```

**Body:**
```json
{
  "agent_version": "0.1.0",
  "ip_address": "192.168.1.100"
}
```

### Submit Metrics

```
POST /api/v1/gateway/metrics
X-Agent-Key: <api_key>
```

**Body:**
```json
{
  "metrics": [
    {"name": "cpu_percent", "value": 45.2, "unit": "%"},
    {"name": "memory_percent", "value": 62.1, "unit": "%", "tags": {"region": "us-east"}}
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "ingested": 2
}
```

### Submit Inventory

```
POST /api/v1/gateway/inventory
X-Agent-Key: <api_key>
```

**Body:**
```json
{
  "system_info": {
    "hostname": "web-server-01",
    "os_type": "linux",
    "os_version": "Linux 6.12.63",
    "cpu_model": "Intel i5-10300H",
    "cpu_cores": 8,
    "ram_total_gb": 15.49,
    "disk_total_gb": 476.94,
    "ip_addresses": ["192.168.1.100"],
    "mac_addresses": ["aa:bb:cc:dd:ee:ff"]
  },
  "software": [
    {"name": "nginx", "version": "1.24.0", "publisher": "Nginx Inc"}
  ]
}
```

**Response:**
```json
{
  "status": "ok",
  "asset_id": "uuid"
}
```

---

## Monitoring

All endpoints require `Authorization: Bearer <token>`.

### Query Metrics

```
GET /api/v1/monitoring/metrics?metric_name=cpu_percent&agent_id=uuid&start=ISO8601&end=ISO8601&bucket_seconds=300
```

All query parameters are optional. Defaults to last hour, all agents, all metrics.

**Response:**
```json
[
  {
    "time_bucket": "2026-02-16T10:00:00+00:00",
    "metric_name": "cpu_percent",
    "agent_id": "uuid",
    "avg_value": 45.2,
    "min_value": 30.1,
    "max_value": 78.5
  }
]
```

### Status Overview

```
GET /api/v1/monitoring/status
```

**Response:**
```json
{
  "total_agents": 5,
  "online_agents": 4,
  "offline_agents": 1,
  "total_assets": 5,
  "active_alerts": 2,
  "metrics_last_hour": 1500
}
```

---

## Assets

All endpoints require `Authorization: Bearer <token>`.

### List Assets

```
GET /api/v1/assets
```

### Get Asset Detail

```
GET /api/v1/assets/{asset_id}
```

Returns full asset info including software inventory.

### Get Asset Software

```
GET /api/v1/assets/{asset_id}/software
```

Returns just the software list for an asset.

---

## Alerting

All endpoints require `Authorization: Bearer <token>`.

### List Alert Rules

```
GET /api/v1/alerting/rules
```

### Create Alert Rule

```
POST /api/v1/alerting/rules
```

**Body:**
```json
{
  "name": "High CPU Alert",
  "description": "Alert when CPU exceeds 80%",
  "metric_name": "cpu_percent",
  "condition": "gt",
  "threshold": 80.0,
  "duration_seconds": 60,
  "agent_id": null,
  "severity": "warning",
  "notify_email": true
}
```

Condition values: `gt` (greater than), `gte` (greater or equal), `lt` (less than), `lte` (less or equal), `eq` (equal).

Severity values: `info`, `warning`, `critical`.

Set `agent_id` to `null` to apply the rule across all agents, or to a specific agent UUID.

### Update Alert Rule

```
PUT /api/v1/alerting/rules/{rule_id}
```

**Body:** Any subset of the create fields.

### Delete Alert Rule

```
DELETE /api/v1/alerting/rules/{rule_id}
```

### List Alerts

```
GET /api/v1/alerting/alerts?status=firing
```

Status filter is optional. Values: `firing`, `acknowledged`, `resolved`.

### Acknowledge Alert

```
POST /api/v1/alerting/alerts/{alert_id}/acknowledge
```

### Resolve Alert

```
POST /api/v1/alerting/alerts/{alert_id}/resolve
```

---

## Runbooks

A runbook is an ordered list of steps. Executions run in a Celery worker, so
`POST /api/v1/runbooks/{id}/execute` returns immediately with status `approved`
(queued) or `pending_approval`; poll the execution or its steps for progress.

| Method | Path | Role |
|---|---|---|
| GET/POST | `/api/v1/runbooks` | any / admin, operator |
| GET/PUT/DELETE | `/api/v1/runbooks/{id}` | any / admin, operator |
| POST | `/api/v1/runbooks/{id}/execute` | admin, operator |
| GET | `/api/v1/runbooks/{id}/executions` | any |
| GET | `/api/v1/runbooks/executions/{exec_id}/steps` | any |
| POST | `/api/v1/runbooks/executions/{exec_id}/approve` | admin |
| POST | `/api/v1/runbooks/executions/{exec_id}/cancel` | admin, operator |

### Step types

Each step is `{"name", "action_type", "parameters", "on_failure"}`. `on_failure`
is `stop` (default: fail the execution) or `continue` (record the failure, run the
next step). Parameters are validated when the runbook is saved.

| `action_type` | Parameters | Result | Fails when |
|---|---|---|---|
| `remote_action` | `agent_id`, `action` (a remote action type), `parameters`, `timeout_seconds` (10–1800, default 300) | `{action_id, status, result}` | the agent reports failure, exits non-zero, or doesn't finish in time |
| `webhook` | `url`, `method` (default `POST`), `headers`, `body` (sent as JSON), `timeout_seconds` (1–30) | `{status_code, body}` | non-2xx response, or the URL targets a non-public address |
| `delay` | `seconds` (0–3600) | `{seconds}` | — |
| `condition` | `step` (index of an earlier step), `path` (dot path into its result), `operator` (`eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `contains`), `value` | `{actual, passed}` | the comparison is false |

Example: restart a service, then confirm the site is healthy.

```json
[
  {"name": "Restart nginx", "action_type": "remote_action",
   "parameters": {"agent_id": "…", "action": "restart_service", "parameters": {"service_name": "nginx"}}},
  {"name": "Wait", "action_type": "delay", "parameters": {"seconds": 10}},
  {"name": "Health check", "action_type": "webhook",
   "parameters": {"url": "https://example.com/health", "method": "GET"}},
  {"name": "Is 200", "action_type": "condition",
   "parameters": {"step": 2, "path": "status_code", "operator": "eq", "value": 200}}
]
```

**Permissions:** only admins can add steps that use admin-only remote actions
(`custom_script`). When an operator runs such a runbook, the execution waits for
admin approval. Executions fire the `runbook.started`, `runbook.completed` and
`runbook.failed` webhook events.

---

## Dashboard WebSocket

```
WebSocket /api/v1/dashboard/ws?token=<access_token>
```

Connects to a real-time feed of updates for the current tenant. Messages are JSON objects:

```json
{"type": "metrics", "agent_id": "uuid", "count": 5}
```

Send `"ping"` to keep the connection alive; server responds with `{"type": "pong"}`.

---

## Health Check

```
GET /health
```

No authentication required.

```json
{
  "status": "healthy",
  "service": "OpsCentral"
}
```
