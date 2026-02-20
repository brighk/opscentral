# OpsCentral Documentation

OpsCentral is an all-in-one IT operations platform for small and mid-sized businesses (10-200 employees). It replaces multiple separate tools — monitoring, asset tracking, alerting, and notifications — with a single platform that features a consumer-grade UI.

## Documentation Index

| Document | Description |
|---|---|
| [Getting Started](getting-started.md) | Quick setup guide — server + first agent in 10 minutes |
| [Server Guide](server-guide.md) | Full server installation, configuration, and administration |
| [Agent Guide](agent-guide.md) | Agent installation on Linux, Windows, and macOS |
| [Architecture](architecture.md) | How OpsCentral works internally |
| [API Reference](api-reference.md) | REST API endpoints for integrations |
| [Roadmap](roadmap.md) | What's planned and what can be added |

## Quick Overview

```
┌─────────────────────────────────────────────────┐
│           OpsCentral Server                     │
│                                                 │
│  React Dashboard  ←→  FastAPI Backend           │
│                       ├── PostgreSQL (data)     │
│                       ├── Redis (real-time)     │
│                       └── Celery (background)   │
└────────────────────────┬────────────────────────┘
                         │ HTTPS
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
     ┌─────────┐   ┌─────────┐   ┌─────────┐
     │  Agent  │   │  Agent  │   │  Agent  │
     │ Linux   │   │ Windows │   │ macOS   │
     └─────────┘   └─────────┘   └─────────┘
```

You run **one server**. You install **agents** on every machine you want to monitor. Agents collect metrics (CPU, memory, disk, network), discover hardware and software, and send everything to the server over HTTP. The server stores, aggregates, evaluates alert rules, and presents it all through a web dashboard.
