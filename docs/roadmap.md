# Roadmap — What Can Be Added

OpsCentral currently covers the MVP: agent-based monitoring, asset discovery, alerting, and a real-time dashboard. Below is everything that can be added, organized by category and priority.

---

## High Priority — Natural Extensions of What Exists

### Process Monitoring

The agent already uses `psutil` which has `psutil.process_iter()`. Adding process monitoring would let users:

- See top processes by CPU/memory on each asset
- Alert when a specific process dies (e.g., nginx, postgres)
- Alert when a process consumes too much memory
- Track process start/stop history

**Effort:** Small. Add a new collector and a process list endpoint.

### Service Health Checks

Beyond system metrics, check whether services are actually responding:

- HTTP endpoint checks (is `https://myapp.com/health` returning 200?)
- TCP port checks (is port 5432 open and accepting connections?)
- DNS resolution checks
- Custom script checks (run a user-defined script, check exit code)

**Effort:** Medium. New collector type + scheduling + new alert rule conditions.

### Log Collection & Search

Collect logs from monitored machines and make them searchable:

- Tail syslog, journald, or application log files
- Forward to the server, store in PostgreSQL or a dedicated log store
- Full-text search in the dashboard
- Alert on log patterns (e.g., "ERROR" appears more than 10 times in 5 minutes)

**Effort:** Large. Needs log ingestion pipeline, storage strategy, and search UI.

### Dashboard Customization

Currently the dashboard has a fixed layout. Adding customization would let users:

- Create custom dashboards with drag-and-drop widgets
- Choose which metrics/agents to display per widget
- Save multiple dashboards (e.g., "Production Overview", "Database Servers")
- Set a dashboard as the default

**Effort:** Medium. Widget configuration model + drag-and-drop UI library.

### Metric Retention Policies

Right now all metrics are stored forever. Add:

- Automatic downsampling (keep per-minute data for 7 days, per-hour for 90 days, per-day for 2 years)
- TimescaleDB continuous aggregates (already supported by the database)
- Configurable retention per tenant/plan

**Effort:** Small. TimescaleDB handles most of this natively.

---

## Medium Priority — New Capabilities

### Vulnerability Scanning

Scan the software inventory for known vulnerabilities:

- Cross-reference installed packages against CVE databases (NVD, OSV)
- Show vulnerability count per asset with severity breakdown
- Alert on new critical/high CVEs affecting installed software
- Track remediation (did the package get updated?)

**Effort:** Medium. Needs CVE database integration (OSV API is free and good).

### Patch Management

Track which systems need updates and manage the update process:

- Show available updates per system (agent queries the package manager)
- One-click or scheduled patch deployment (agent runs `apt upgrade`, `pacman -Syu`, etc.)
- Patch compliance reporting (what percentage of systems are up to date?)
- Rollback tracking

**Effort:** Large. Running commands remotely requires a bidirectional agent channel.

### Remote Command Execution

Execute commands on managed systems from the dashboard:

- Run ad-hoc commands (restart a service, check a config file)
- Predefined "actions" (restart nginx, clear disk cache, rotate logs)
- Audit trail of who ran what, when, and the output

**Effort:** Medium. Needs a reverse channel (WebSocket from agent to server or server-initiated tasks via polling).

### User & Access Management

Currently each tenant has users but no role-based access control:

- Roles: Admin, Operator (can ack alerts), Viewer (read-only)
- Invite users by email
- Per-team dashboards and alert routing
- Audit log of user actions

**Effort:** Medium. RBAC model + middleware + UI for user management.

### SSO / SAML / OAuth

Enterprise customers expect Single Sign-On:

- Google Workspace login
- Microsoft Entra ID (Azure AD)
- SAML 2.0 for enterprise identity providers
- OIDC support

**Effort:** Medium. Libraries like `python-social-auth` or `authlib` handle the protocols.

### Notification Channels

Currently only email notifications. Add:

- **Slack** — send alerts to a Slack channel via webhook
- **Microsoft Teams** — same via Teams webhook
- **PagerDuty** — escalate critical alerts
- **Discord** — webhook integration
- **SMS** — via Twilio
- **Custom webhook** — POST JSON to any URL

**Effort:** Small per channel. The notification service just needs additional dispatch methods.

### Network Topology / Discovery

Automatically discover the network:

- Map which agents can reach each other
- Discover services on the local network (port scanning)
- Visualize network topology in the dashboard
- Alert on new devices appearing on the network

**Effort:** Large. Network scanning, topology visualization, and security implications.

---

## Lower Priority — Nice to Have

### Compliance Reporting

Generate reports for compliance frameworks:

- CIS Benchmarks (check system configurations against best practices)
- SOC 2 evidence collection
- Custom compliance checklists
- PDF/CSV report export
- Scheduled report emails

**Effort:** Large. Needs compliance rule definitions + reporting engine.

### Billing & Subscription Management

For running OpsCentral as a SaaS:

- Stripe integration for subscription billing
- Usage tracking (asset count per tenant)
- Plan upgrade/downgrade flows
- Invoice generation
- Trial period management

**Effort:** Medium. Stripe handles most of the payment complexity.

### Mobile App

A mobile companion for on-the-go monitoring:

- React Native app (share code with web)
- Push notifications for alerts
- Quick status view of all systems
- Acknowledge alerts from phone

**Effort:** Large. Separate application, push notification infrastructure.

### Agent Auto-Update

The agent currently has a static version. Add self-update capability:

- Agent checks for new versions periodically
- Downloads and replaces itself
- Rolls back if the new version crashes
- Server can push update requests

**Effort:** Medium. Needs signed release artifacts and a careful update mechanism.

### Container & Kubernetes Monitoring

Monitor containerized workloads:

- Docker container metrics (CPU, memory, network per container)
- Docker image inventory
- Kubernetes pod/node/deployment status (via kubelet API)
- Container log forwarding

**Effort:** Large. New collector + Kubernetes API integration.

### Database Monitoring

Specialized monitoring for databases:

- PostgreSQL: connections, query latency, replication lag, table sizes
- MySQL: similar metrics
- Redis: memory, connections, keyspace stats
- MongoDB: operation counters, replication status

**Effort:** Medium per database. Separate collector per database type.

### Uptime Monitoring (External)

Monitor services from the outside, not from the host:

- HTTP/HTTPS endpoint monitoring from the server
- Response time tracking
- SSL certificate expiration alerts
- Status page generation (public status page for your services)

**Effort:** Medium. New monitoring module that runs on the server, not the agent.

### Configuration Management

Track and alert on configuration changes:

- Monitor specific config files for changes (nginx.conf, sshd_config, etc.)
- Show diffs when configs change
- Alert on unauthorized changes
- Configuration backup

**Effort:** Medium. File watching collector + diff storage.

### Integrations & Webhooks

Let external systems push data into OpsCentral or pull data out:

- Incoming webhooks (receive alerts from other tools)
- Outgoing webhooks (trigger external actions on alert)
- REST API for custom integrations
- Grafana data source plugin (use OpsCentral as a Grafana backend)

**Effort:** Varies. The API already exists; Grafana plugin is medium effort.

---

## Implementation Priority Suggestion

If building these out in order, here's a suggested sequence based on customer value and technical dependencies:

| Phase | Features | Why |
|---|---|---|
| **Phase 2** | Process monitoring, service health checks, notification channels (Slack/Teams/webhook), metric retention policies | High value, builds directly on existing infrastructure |
| **Phase 3** | Vulnerability scanning, user/access management, dashboard customization, uptime monitoring | Differentiation from basic monitoring tools |
| **Phase 4** | Remote command execution, patch management, log collection, compliance reporting | Enterprise features, higher complexity |
| **Phase 5** | SSO/SAML, billing/subscriptions, container monitoring, database monitoring, mobile app | Scale and monetization features |

---

## Contributing Ideas

The architecture is designed to make adding new features straightforward:

- **New metric type**: Add a collector in `agent/opscentral_agent/collectors/`, the agent picks it up automatically
- **New alert condition**: Extend the `CONDITION_OPS` dict in `backend/app/tasks/alert_tasks.py`
- **New notification channel**: Add a dispatch method in `backend/app/notifications/service.py`
- **New API endpoint**: Create a new module under `backend/app/` with models, schemas, and routes, then register the router in `app/main.py`
- **New dashboard page**: Create a page component in `frontend/src/pages/`, add a route in `App.tsx`, add a nav item in `AppLayout.tsx`
