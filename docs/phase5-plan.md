# OpsCentral Phase 5 — Integrations, Automation & Incidents

## Context

Phases 1-4 built a full production-ready IT ops SaaS: monitoring, alerting, assets, health checks, vulnerabilities, RBAC, dashboards, uptime, billing, reporting, compliance, remote actions, API keys. 69 tests passing, 19 frontend pages, 20+ backend modules. Phase 5 adds the features that make OpsCentral sticky for paying teams: integrations with external tools, automated remediation, and incident management.

## Implementation Order

1. **Webhooks & Integration Platform** — foundational event system, no dependencies
2. **Runbooks & Automation** — builds on remote actions (Phase 4) + webhooks (Step 1)
3. **Incident Management** — builds on alerts, integrations, and team concepts
4. **On-Call Schedules & Escalations** — extends incidents (Step 3) with routing

---

## Step 1: Webhooks & Integration Platform

### New files
- `app/integrations/` module
  - `__init__.py`
  - `models.py`:
    - `WebhookEndpoint` — tenant_id, name, url, secret (HMAC signing), event_types (JSON list), is_active, failure_count, last_triggered_at, last_status_code
    - `WebhookDelivery` — endpoint_id, event_type, payload, status_code, response_body, duration_ms, created_at
    - `ExternalIntegration` — tenant_id, provider (pagerduty/jira/opsgenie/servicenow), config (encrypted JSON), is_active
  - `schemas.py`:
    - `WebhookEndpointCreate` — name, url, secret (optional, auto-generate if omitted), event_types
    - `WebhookEndpointResponse`, `WebhookEndpointUpdate`
    - `WebhookDeliveryResponse`
    - `ExternalIntegrationCreate` — provider, config
    - `ExternalIntegrationResponse`
  - `routes.py`:
    - CRUD `/api/v1/webhooks` — list, create, update, delete (admin/operator)
    - GET `/api/v1/webhooks/{id}/deliveries` — delivery history with status
    - POST `/api/v1/webhooks/{id}/test` — send test event
    - GET `/api/v1/webhooks/event-types` — list available event types
    - CRUD `/api/v1/integrations` — list, create, update, delete (admin)
    - POST `/api/v1/integrations/{id}/test` — test connection
  - `dispatcher.py`:
    - `dispatch_webhook(tenant_id, event_type, payload)` — fan-out to matching endpoints
    - HMAC-SHA256 signature in `X-OC-Signature` header
    - Retry logic: 3 attempts with exponential backoff (1s, 5s, 25s)
    - Auto-disable endpoint after 10 consecutive failures
  - `event_types.py`:
    - `EVENT_TYPES` dict — all subscribable events:
      - `alert.fired`, `alert.resolved`, `alert.acknowledged`
      - `agent.online`, `agent.offline`
      - `vulnerability.detected`, `vulnerability.resolved`
      - `health_check.down`, `health_check.up`
      - `asset.created`, `asset.deleted`
      - `incident.created`, `incident.resolved` (added in Step 3)
      - `runbook.started`, `runbook.completed`, `runbook.failed` (added in Step 2)
  - `providers/` — external integration adapters
    - `__init__.py`
    - `base.py` — `IntegrationProvider` abstract base class (send_alert, create_ticket, resolve_ticket)
    - `pagerduty.py` — PagerDuty Events API v2 (trigger, acknowledge, resolve)
    - `jira.py` — Jira Cloud REST API (create issue from alert, link to OpsCentral)
    - `opsgenie.py` — OpsGenie Alert API
    - `servicenow.py` — ServiceNow Incident API
- `app/tasks/webhook_tasks.py`:
  - `deliver_webhook` — async HTTP POST with retry
  - `cleanup_old_deliveries` — daily, keep 30 days

### Modify
- `app/tasks/celery_app.py` — add beat: cleanup-webhook-deliveries (daily 4 AM)
- `app/main.py` — register integrations router
- `app/tasks/alert_tasks.py` — after firing/resolving alert, call `dispatch_webhook("alert.fired", ...)`
- `app/agents/routes.py` — in heartbeat stale detection, call `dispatch_webhook("agent.offline", ...)`
- `app/config.py` — add `WEBHOOK_TIMEOUT_SECONDS: int = 10`, `WEBHOOK_MAX_RETRIES: int = 3`
- `pyproject.toml` — add `cryptography>=43.0` (for HMAC + config encryption)

### Frontend
- `src/api/integrations.ts` — webhooks CRUD, deliveries, integrations CRUD
- `src/pages/IntegrationsPage.tsx`:
  - Tabs: "Webhooks" | "External Integrations"
  - Webhooks: table with name/url/status/event count, create modal, delivery log drawer
  - Integrations: provider cards (PagerDuty, Jira, OpsGenie, ServiceNow) with setup wizard
- `App.tsx` + `AppLayout.tsx` — add `/integrations` route + nav (IconPlugConnected)

### Tests (`tests/test_phase5_webhooks.py`)
- test_create_webhook_endpoint
- test_list_webhook_endpoints
- test_update_webhook_endpoint
- test_delete_webhook_endpoint
- test_test_webhook_sends_request (mock httpx)
- test_list_event_types
- test_webhook_hmac_signature
- test_create_external_integration
- test_viewer_cannot_create_webhook (RBAC)

---

## Step 2: Runbooks & Automation

### New files
- `app/runbooks/` module
  - `__init__.py`
  - `models.py`:
    - `Runbook` — tenant_id, name, description, steps (JSON array of step definitions), trigger_type (manual/alert_rule), trigger_config (JSON), is_active, requires_approval, created_by
    - `RunbookStep` schema (within JSON): action_type, parameters, on_failure (continue/abort/skip), timeout_seconds, delay_seconds (wait before executing)
    - `RunbookExecution` — runbook_id, tenant_id, trigger (manual/auto), triggered_by (user_id or alert_id), status (pending_approval/approved/running/completed/failed/cancelled), started_at, completed_at, approval_by, approved_at
    - `RunbookStepExecution` — execution_id, step_index, action_type, status (pending/running/completed/failed/skipped), result (JSON), error, started_at, completed_at
  - `schemas.py`:
    - `RunbookCreate` — name, description, steps[], trigger_type, trigger_config, requires_approval
    - `RunbookResponse`, `RunbookUpdate`
    - `RunbookExecutionResponse`, `RunbookStepExecutionResponse`
    - `RunbookTriggerRequest` — optional parameters override
  - `routes.py`:
    - CRUD `/api/v1/runbooks` — list, create, update, delete (admin/operator)
    - POST `/api/v1/runbooks/{id}/execute` — manual trigger (operator/admin)
    - GET `/api/v1/runbooks/{id}/executions` — execution history
    - GET `/api/v1/runbooks/executions/{exec_id}` — execution detail with step results
    - POST `/api/v1/runbooks/executions/{exec_id}/approve` — approve pending execution (admin)
    - POST `/api/v1/runbooks/executions/{exec_id}/cancel` — cancel running execution
  - `engine.py` — `RunbookEngine`:
    - `execute_runbook(execution_id)` — iterate steps, dispatch remote actions, wait for results
    - Step execution: maps runbook steps to remote action creation + polling
    - Handles on_failure policies (continue/abort/skip)
    - Honors delay_seconds between steps
    - Emits webhook events: `runbook.started`, `runbook.completed`, `runbook.failed`
- `app/tasks/runbook_tasks.py`:
  - `execute_runbook_async` — Celery task wrapping RunbookEngine
  - `check_alert_triggered_runbooks` — called from alert evaluation, checks if any runbooks should auto-trigger

### Modify
- `app/tasks/celery_app.py` — autodiscover includes runbook_tasks
- `app/main.py` — register runbooks router
- `app/tasks/alert_tasks.py` — after alert fires, check for auto-trigger runbooks
- `app/alerting/routes.py` — add optional `runbook_id` to AlertRuleCreate/Update (link rule → runbook)
- `app/alerting/models.py` — add `runbook_id: UUID | None` to AlertRule

### Frontend
- `src/api/runbooks.ts` — runbooks CRUD, executions, approve/cancel
- `src/pages/RunbooksPage.tsx`:
  - Runbook list with status badges
  - Create/edit modal with step builder (drag-and-drop step ordering)
    - Each step: select action type, configure parameters, set on_failure, set delay
  - Execution history table
  - Execution detail view: step-by-step progress with status, result, timing
  - Approval banner for pending executions
- `src/pages/AlertsPage.tsx` — add "Attach Runbook" option to alert rule create/edit
- `App.tsx` + `AppLayout.tsx` — add `/runbooks` route + nav (IconBook2)

### Tests (`tests/test_phase5_runbooks.py`)
- test_create_runbook
- test_list_runbooks
- test_execute_runbook_manual
- test_execution_requires_approval
- test_approve_execution
- test_cancel_execution
- test_execution_detail_with_steps
- test_viewer_cannot_execute (RBAC)
- test_delete_runbook

---

## Step 3: Incident Management

### New files
- `app/incidents/` module
  - `__init__.py`
  - `models.py`:
    - `Incident` — tenant_id, title, description, severity (critical/high/medium/low), status (investigating/identified/monitoring/resolved/postmortem), source (manual/alert/integration), source_id (alert_id if auto-created), assigned_to (user_id), commander_id (user_id), created_by, started_at, resolved_at, duration_seconds (computed)
    - `IncidentUpdate` — incident_id, author_id, message, status_change (old→new or null), is_internal (visible to team only vs public status page), created_at
    - `IncidentTag` — incident_id, key, value (e.g., service:api, env:prod)
    - `Postmortem` — incident_id, summary, root_cause, timeline_md, action_items (JSON array), impact_description, published, published_at
  - `schemas.py`:
    - `IncidentCreate` — title, description, severity, assigned_to (optional)
    - `IncidentResponse`, `IncidentUpdate` (for PATCH)
    - `IncidentUpdateCreate` — message, status (optional, triggers transition)
    - `IncidentUpdateResponse`
    - `PostmortemCreate`, `PostmortemResponse`
    - `IncidentStatsResponse` — open_count, mttr_minutes, by_severity, by_status
  - `routes.py`:
    - POST `/api/v1/incidents` — create incident (operator/admin)
    - GET `/api/v1/incidents` — list with filters (status, severity, assigned_to, date range)
    - GET `/api/v1/incidents/{id}` — detail with updates timeline
    - PATCH `/api/v1/incidents/{id}` — update severity, assignment, status
    - POST `/api/v1/incidents/{id}/updates` — add timeline update (with optional status change)
    - POST `/api/v1/incidents/{id}/resolve` — resolve with summary
    - GET `/api/v1/incidents/{id}/postmortem` — get postmortem
    - POST `/api/v1/incidents/{id}/postmortem` — create/update postmortem
    - GET `/api/v1/incidents/stats` — MTTR, counts by severity/status
  - `service.py`:
    - `create_incident_from_alert(alert)` — auto-create incident when critical alert fires
    - `auto_resolve_incident(alert)` — resolve linked incident when alert resolves
    - `calculate_mttr(tenant_id)` — mean time to resolve

### Modify
- `app/main.py` — register incidents router
- `app/tasks/alert_tasks.py` — on critical alert fire, call `create_incident_from_alert()`
- `app/integrations/event_types.py` — add `incident.created`, `incident.updated`, `incident.resolved`
- `app/integrations/dispatcher.py` — dispatch incident events
- `app/uptime/routes.py` — public status page now shows active incidents

### Frontend
- `src/api/incidents.ts` — incidents CRUD, updates, postmortem, stats
- `src/pages/IncidentsPage.tsx`:
  - Incident list with severity/status badges, assigned user, duration
  - Filters: status, severity, date range
  - Stats bar: open incidents, MTTR, by severity
  - Create incident modal
- `src/pages/IncidentDetailPage.tsx`:
  - Header: title, severity, status, assigned to, commander
  - Timeline: chronological updates with status changes highlighted
  - Add update form (message + optional status change)
  - Sidebar: tags, linked alerts, linked runbook executions
  - Postmortem tab: markdown editor for root cause, timeline, action items
- `src/pages/DashboardPage.tsx` — add active incidents widget
- `App.tsx` + `AppLayout.tsx` — add `/incidents` route + nav (IconUrgent)

### Tests (`tests/test_phase5_incidents.py`)
- test_create_incident
- test_list_incidents_with_filters
- test_get_incident_detail
- test_add_incident_update
- test_update_incident_status_via_update
- test_resolve_incident
- test_create_postmortem
- test_incident_stats
- test_viewer_cannot_create_incident (RBAC)
- test_auto_create_from_critical_alert

---

## Step 4: On-Call Schedules & Escalations

### New files
- `app/oncall/` module
  - `__init__.py`
  - `models.py`:
    - `OnCallSchedule` — tenant_id, name, timezone, rotation_type (daily/weekly/custom), participants (JSON array of user_ids with order), start_date, handoff_time (e.g., "09:00"), is_active
    - `OnCallOverride` — schedule_id, user_id, start_at, end_at, reason (e.g., "vacation cover")
    - `EscalationPolicy` — tenant_id, name, steps (JSON array), repeat_count (0=no repeat), is_default
    - `EscalationStep` schema (within JSON): delay_minutes, targets (array of: type user/schedule/integration, id), notify_via (email/slack/pagerduty)
  - `schemas.py`:
    - `OnCallScheduleCreate`, `OnCallScheduleResponse`, `OnCallScheduleUpdate`
    - `OnCallOverrideCreate`, `OnCallOverrideResponse`
    - `EscalationPolicyCreate`, `EscalationPolicyResponse`, `EscalationPolicyUpdate`
    - `CurrentOnCallResponse` — user_id, user_name, schedule_name, until
  - `routes.py`:
    - CRUD `/api/v1/oncall/schedules` — list, create, update, delete (admin)
    - GET `/api/v1/oncall/schedules/{id}/current` — who is currently on call
    - GET `/api/v1/oncall/schedules/{id}/timeline` — visual timeline (next 7/30 days)
    - CRUD `/api/v1/oncall/overrides` — create, list, delete
    - CRUD `/api/v1/oncall/policies` — escalation policy CRUD (admin)
    - GET `/api/v1/oncall/whoami` — "am I on call right now?"
  - `resolver.py`:
    - `get_current_oncall(schedule_id, at_time)` — resolves rotation + overrides to current user
    - `run_escalation(policy_id, incident_id)` — step through policy, notify at each level
  - `notifier.py`:
    - `notify_oncall(incident, escalation_step)` — send notification to on-call via configured channel
    - Channels: email, Slack DM, PagerDuty, push notification placeholder
- `app/tasks/oncall_tasks.py`:
  - `run_escalations` — every 60s, check incidents without response, escalate
  - `send_handoff_notifications` — daily, notify next on-call person 30min before handoff

### Modify
- `app/tasks/celery_app.py` — add beats: run-escalations (60s), send-handoff-notifications (daily)
- `app/main.py` — register oncall router
- `app/incidents/service.py` — when incident created, look up escalation policy, start escalation
- `app/incidents/routes.py` — PATCH incident: if assigned_to changes, notify new assignee
- `app/alerting/models.py` — add `escalation_policy_id: UUID | None` to AlertRule

### Frontend
- `src/api/oncall.ts` — schedules, overrides, policies CRUD
- `src/pages/OnCallPage.tsx`:
  - "Who's On Call" banner showing current on-call per schedule
  - Schedule list with rotation visualization
  - Schedule detail: calendar view showing rotation + overrides
  - Override create modal (date picker, user select, reason)
  - Escalation policy builder: step editor with delay + target selectors
- `src/pages/IncidentDetailPage.tsx` — show escalation timeline (who was notified when)
- `App.tsx` + `AppLayout.tsx` — add `/oncall` route + nav (IconPhoneCall)

### Tests (`tests/test_phase5_oncall.py`)
- test_create_schedule
- test_get_current_oncall
- test_rotation_daily
- test_override_takes_precedence
- test_create_escalation_policy
- test_escalation_steps
- test_whoami_endpoint
- test_handoff_timeline
- test_viewer_cannot_create_schedule (RBAC)

---

## Model registrations (after all steps)

Add to `conftest.py` and `alembic/env.py`:
```python
from app.integrations.models import WebhookEndpoint, WebhookDelivery, ExternalIntegration
from app.runbooks.models import Runbook, RunbookExecution, RunbookStepExecution
from app.incidents.models import Incident, IncidentUpdate, IncidentTag, Postmortem
from app.oncall.models import OnCallSchedule, OnCallOverride, EscalationPolicy
```

## Dependency additions (`pyproject.toml`)
```toml
"cryptography>=43.0",  # HMAC signatures, config encryption
```

## Config additions (`app/config.py`)
```python
WEBHOOK_TIMEOUT_SECONDS: int = 10
WEBHOOK_MAX_RETRIES: int = 3
PAGERDUTY_ROUTING_KEY: str = ""  # optional global default
```

## Verification

After each step:
1. `pytest tests/ -q` — all tests pass (no regressions)
2. `npx tsc --noEmit` — frontend compiles clean
3. `npx vite build` — production build succeeds
4. Step-specific test file passes

Final: 69 existing + ~38 new ≈ ~107 tests all passing.
4 new frontend pages (Integrations, Runbooks, Incidents + IncidentDetail, OnCall).
Total: 23 frontend pages, 25+ backend modules.

## Implementation notes

- **Webhook dispatcher** should be async (Celery task) to avoid blocking request handlers. Alert/agent routes call `dispatch_webhook.delay()` not `dispatch_webhook()`.
- **Runbook engine** runs as a long-lived Celery task. Each step creates a RemoteAction (from Phase 4), waits for completion via polling, then proceeds.
- **Incident auto-creation** should deduplicate: don't create a new incident if there's already an open incident linked to the same alert rule.
- **On-call resolver** must handle timezone correctly. All rotations stored in tenant timezone, resolved to UTC for comparisons.
- **Escalation** uses a "claim or escalate" model: if the on-call person acknowledges the incident within the delay window, escalation stops. Otherwise, it proceeds to the next step.
- **HMAC signatures** for webhooks: `HMAC-SHA256(endpoint.secret, JSON payload)` in `X-OC-Signature` header. Recipients can verify authenticity.
