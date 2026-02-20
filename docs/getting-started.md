# Getting Started

Get OpsCentral running with a server and your first agent in about 10 minutes.

## Prerequisites

- **Server machine**: Linux with Docker and Docker Compose installed
- **Python 3.12+** on the server (for the backend)
- **Node.js 18+** on the server (for the frontend, development only)
- **Python 3.10+** on any machine where you install the agent

## Step 1: Start the Databases

```bash
cd OpsCentral
docker compose up -d
```

This starts:
- **TimescaleDB** (PostgreSQL 16 with time-series extensions) on port 5432
- **Redis 7** on port 6379

Verify they're healthy:

```bash
docker compose ps
```

Both should show `healthy` status.

## Step 2: Set Up the Backend

```bash
# Create a virtual environment
cd backend
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify: open `http://localhost:8000/health` — you should see `{"status": "healthy"}`.

The full API docs are at `http://localhost:8000/docs` (Swagger UI).

## Step 3: Start the Frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

## Step 4: Create Your Account

1. Go to `http://localhost:5173/register`
2. Fill in your name, company name, email, and password
3. You'll be logged in and see an empty dashboard

## Step 5: Install Your First Agent

### Option A: Through the Dashboard

1. Click **Agents** in the sidebar
2. Click **Install Agent**
3. Enter a hostname for the machine, pick the OS
4. Copy the generated API key

### Option B: Manual Setup

```bash
# On your server, while logged in, register an agent via the API:
curl -X POST http://localhost:8000/api/v1/agents/register \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hostname": "my-server-01", "os_type": "linux"}'

# Response includes agent_id and api_key
```

### Run the Agent

On the machine you want to monitor:

```bash
cd OpsCentral/agent
pip install -e .

# Set environment variables
export OC_API_KEY="the-api-key-from-step-above"
export OC_SERVER_URL="http://your-server-ip:8000"

# Run the agent
opscentral-agent
```

You can also create a config file at `/etc/opscentral/agent.yml`:

```yaml
server_url: http://your-server-ip:8000
api_key: your-api-key-here
collect_interval: 60
inventory_interval: 300
log_level: INFO
```

## Step 6: See Your Data

Go back to the dashboard at `http://localhost:5173`. Within 60 seconds you should see:

- **Dashboard**: CPU and memory charts populating, agent count updating
- **Agents**: Your agent showing as "Online" with a green dot
- **Assets**: An asset auto-created from the agent's inventory report
- **Monitoring**: Metric charts for CPU, memory, disk, network

## Step 7: Create an Alert Rule

1. Go to **Alerts** → click **New Rule**
2. Example: "High CPU Alert" — metric `cpu_percent`, condition `greater than`, threshold `80`
3. Set severity to `warning`, enable email notifications
4. Click **Create Rule**

The server evaluates all rules every 60 seconds. If CPU goes above 80%, an alert fires and appears on the dashboard.

## Optional: Start Background Workers

For alert evaluation and email notifications to work automatically:

```bash
# Terminal 1: Celery worker (processes tasks)
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info

# Terminal 2: Celery beat (schedules tasks)
cd backend
source .venv/bin/activate
celery -A app.tasks.celery_app beat --loglevel=info
```

## Quick Reference

| Command | What it does |
|---|---|
| `make db-up` | Start PostgreSQL + Redis |
| `make db-down` | Stop databases |
| `make dev-backend` | Start backend API server |
| `make dev-frontend` | Start frontend dev server |
| `make dev-agent` | Run agent locally |
| `make dev-celery` | Start Celery worker |
| `make dev-celery-beat` | Start Celery beat scheduler |
| `make db-migrate` | Run database migrations |
| `make test-backend` | Run backend tests |

## Next Steps

- Read the [Server Guide](server-guide.md) for production configuration
- Read the [Agent Guide](agent-guide.md) for deploying agents across your fleet
- Set up alert rules for the metrics that matter to your infrastructure
