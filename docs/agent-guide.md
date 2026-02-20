# Agent Guide

The OpsCentral agent is a lightweight Python process that runs on every machine you want to monitor. It collects system metrics, discovers hardware and installed software, and sends everything to the OpsCentral server over HTTP.

## What the Agent Collects

### Metrics (every 60 seconds by default)

| Category | Metrics | Works On |
|---|---|---|
| **CPU** | `cpu_percent`, `cpu_freq_mhz`, `cpu_count_logical`, `cpu_count_physical` | All |
| **CPU Load** | `load_avg_1m`, `load_avg_5m`, `load_avg_15m` | Linux, macOS |
| **Memory** | `memory_percent`, `memory_used_gb`, `memory_available_gb`, `memory_total_gb`, `swap_percent`, `swap_used_gb` | All |
| **Disk** | `disk_percent`, `disk_used_gb`, `disk_total_gb` (per mount/drive), `disk_read_mb`, `disk_write_mb` | All |
| **Network** | `net_bytes_sent_mb`, `net_bytes_recv_mb`, `net_packets_sent`, `net_packets_recv`, `net_errors_in`, `net_errors_out`, `net_connections` | All |

### Inventory (every 5 minutes by default)

**Hardware information:**
- Hostname, OS type and version
- CPU model and core count
- Total RAM and disk space
- IP addresses and MAC addresses
- Architecture, Python version

**Installed software:** Collected from whatever package manager is available, plus a filesystem scan for software installed outside the package manager.

## Supported Linux Package Managers

The agent tries these in order and uses the first one that works:

| Distro | Package Manager | Command Used |
|---|---|---|
| Arch, Manjaro, EndeavourOS | pacman | `pacman -Q` |
| Debian, Ubuntu, Mint, Pop!_OS | dpkg | `dpkg-query -W` |
| RHEL, CentOS, Fedora, Rocky, Alma | rpm | `rpm -qa` |
| Gentoo, Funtoo | portage | `equery list` → `qlist -Iv` → direct `/var/db/pkg` scan |
| Alpine | apk | `apk list --installed` |
| openSUSE | zypper | `zypper se --installed-only` |
| Void Linux | xbps | `xbps-query -l` |
| NixOS | nix | `nix-env -q` |

### Source-Installed Software

After the package manager scan, the agent also scans these directories for executables not tracked by any package manager:

| Path | What it catches |
|---|---|
| `/usr/local/bin`, `/usr/local/sbin` | Programs installed with `make install`, `cmake --install`, etc. |
| `/opt/*` | Third-party applications (Chrome, CUDA, JetBrains IDEs, etc.) |
| `~/.local/bin` | User-installed tools (pipx, cargo install, go install, etc.) |

For each binary found, the agent tries running `binary --version` to extract a version number. These show up in the asset's software inventory with a `source-installed` label so you can tell them apart from package-managed software.

### Windows Software Discovery

On Windows, the agent reads from:
- `HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` (64-bit programs)
- `HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*` (32-bit programs)
- `HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` (per-user installs)
- `C:\Program Files` and `C:\Program Files (x86)` directory scan for anything not in the registry

### macOS Software Discovery

On macOS, the agent reads from:
- `/Applications/*.app` directory (reads version from `Info.plist`)
- `brew list --versions` (Homebrew packages, if installed)

## Installation

### Prerequisites

- Python 3.10 or higher
- Network access to the OpsCentral server (HTTP/HTTPS)

### Step 1: Register the Agent

Before installing, you need an API key. You can get one from the dashboard (Agents → Install Agent) or via the API:

```bash
curl -X POST https://your-server/api/v1/agents/register \
  -H "Authorization: Bearer YOUR_USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hostname": "web-server-01", "os_type": "linux"}'
```

This returns an `agent_id` and `api_key`. Save the API key — it's the agent's credential.

### Step 2: Install and Run

#### Linux — Quick Install (systemd)

```bash
curl -sSL https://get.opscentral.io/agent | sudo bash -s -- \
  --api-key YOUR_API_KEY \
  --server https://your-server
```

This installs the agent, creates a config file at `/etc/opscentral/agent.yml`, sets up a systemd service, and starts it immediately.

#### Linux — Manual Install

```bash
# Install the package
pip install opscentral-agent
# Or from source:
cd OpsCentral/agent
pip install -e .

# Option 1: Environment variables
export OC_API_KEY="your-api-key"
export OC_SERVER_URL="https://your-server"
opscentral-agent

# Option 2: Config file
sudo mkdir -p /etc/opscentral
sudo tee /etc/opscentral/agent.yml << EOF
server_url: https://your-server
api_key: your-api-key
collect_interval: 60
inventory_interval: 300
log_level: INFO
EOF

opscentral-agent
```

#### Windows — PowerShell

Run PowerShell as Administrator:

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 `
  -ApiKey YOUR_API_KEY `
  -ServerUrl https://your-server
```

Or manually:

```powershell
pip install opscentral-agent

$env:OC_API_KEY = "your-api-key"
$env:OC_SERVER_URL = "https://your-server"
opscentral-agent
```

Config file location on Windows: `C:\ProgramData\OpsCentral\agent.yml`

#### macOS

```bash
pip3 install opscentral-agent

export OC_API_KEY="your-api-key"
export OC_SERVER_URL="https://your-server"
opscentral-agent
```

Config file location: `/etc/opscentral/agent.yml`

## Configuration Reference

The agent loads configuration in this order (later overrides earlier):

1. Config file (`/etc/opscentral/agent.yml` or `C:\ProgramData\OpsCentral\agent.yml`)
2. Environment variables

| Config Key | Env Variable | Default | Description |
|---|---|---|---|
| `server_url` | `OC_SERVER_URL` | `http://localhost:8000` | URL of the OpsCentral server |
| `api_key` | `OC_API_KEY` | (empty) | Agent API key from registration |
| `collect_interval` | `OC_COLLECT_INTERVAL` | `60` | Seconds between metric collections |
| `inventory_interval` | `OC_INVENTORY_INTERVAL` | `300` | Seconds between inventory reports |
| `log_level` | `OC_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Example Config File

```yaml
server_url: https://ops.yourcompany.com
api_key: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2
collect_interval: 30      # collect every 30 seconds for critical servers
inventory_interval: 600   # inventory every 10 minutes
log_level: WARNING        # less verbose logging in production
```

## How It Communicates

The agent makes three types of HTTP POST requests to the server:

### 1. Heartbeat (`POST /api/v1/gateway/heartbeat`)

Sent with every metric collection cycle. Tells the server the agent is alive and updates `last_seen`. If the server doesn't receive a heartbeat for 5 minutes, it fires a "stale agent" alert.

```json
{
  "agent_version": "0.1.0",
  "ip_address": "192.168.1.100"
}
```

### 2. Metrics (`POST /api/v1/gateway/metrics`)

Sends all collected metrics as a batch.

```json
{
  "metrics": [
    {"name": "cpu_percent", "value": 45.2, "unit": "%"},
    {"name": "memory_percent", "value": 62.1, "unit": "%"},
    {"name": "disk_percent", "value": 38.5, "unit": "%", "tags": {"mountpoint": "/"}}
  ]
}
```

### 3. Inventory (`POST /api/v1/gateway/inventory`)

Sends full hardware and software inventory. This auto-creates or updates the corresponding asset in the server.

```json
{
  "system_info": {
    "hostname": "web-server-01",
    "os_type": "linux",
    "os_version": "Linux 6.12.63-1-MANJARO",
    "cpu_model": "Intel Core i5-10300H",
    "cpu_cores": 8,
    "ram_total_gb": 15.49,
    "disk_total_gb": 476.94,
    "ip_addresses": ["192.168.1.100"],
    "mac_addresses": ["aa:bb:cc:dd:ee:ff"]
  },
  "software": [
    {"name": "nginx", "version": "1.24.0"},
    {"name": "python", "version": "3.12.0"},
    {"name": "ollama", "version": "0.12.6", "publisher": "source-installed (/usr/local/bin)"}
  ]
}
```

All requests include the header `X-Agent-Key: <api_key>` for authentication.

## Managing Agents

### Viewing Agent Status

In the dashboard, go to **Agents**. Each agent shows:
- **Online/Offline** status (green = heartbeat within last 3 minutes)
- Last seen timestamp
- OS, version, IP address
- Agent software version

### Deactivating an Agent

Click the trash icon next to an agent, or via API:

```bash
curl -X DELETE https://your-server/api/v1/agents/AGENT_UUID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

This deactivates the agent on the server side. The agent process on the remote machine will still run but its requests will be rejected. Stop the agent process separately:

```bash
# Linux (systemd)
sudo systemctl stop opscentral-agent
sudo systemctl disable opscentral-agent

# Windows
Stop-ScheduledTask -TaskName OpsCentralAgent
Unregister-ScheduledTask -TaskName OpsCentralAgent
```

## Troubleshooting

| Problem | Solution |
|---|---|
| Agent starts but no data in dashboard | Check `OC_SERVER_URL` points to the right server. Check firewall allows the connection. Run with `OC_LOG_LEVEL=DEBUG` to see HTTP errors. |
| "Invalid agent API key" error | The API key doesn't match any active agent. Re-register the agent to get a new key. |
| Agent shows as offline | Check the agent process is running. Check network connectivity. The server marks agents offline if no heartbeat for 3+ minutes. |
| High CPU from the agent | Increase `collect_interval` (default 60s). The CPU collector uses `psutil.cpu_percent(interval=1)` which blocks for 1 second per collection. |
| Permission errors in logs | Some collectors (network connections, certain disk partitions) need root/admin access. Run the agent as root or with appropriate permissions. |
| Software inventory is empty | The agent couldn't find any known package manager. Check that `pacman`, `dpkg-query`, `rpm`, or equivalent is in PATH. |
