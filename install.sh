#!/bin/bash
set -euo pipefail

# OpsCentral Agent Installer
# Usage: curl -sSL https://get.opscentral.io/agent | sudo bash -s -- --api-key YOUR_KEY --server https://your-server.com

API_KEY=""
SERVER_URL=""
INSTALL_DIR="/opt/opscentral"
CONFIG_DIR="/etc/opscentral"

while [[ $# -gt 0 ]]; do
    case $1 in
        --api-key) API_KEY="$2"; shift 2 ;;
        --server) SERVER_URL="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [ -z "$API_KEY" ] || [ -z "$SERVER_URL" ]; then
    echo "Error: --api-key and --server are required"
    echo "Usage: $0 --api-key YOUR_KEY --server https://your-server.com"
    exit 1
fi

echo "==> Installing OpsCentral Agent..."

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "==> Found Python $PYTHON_VERSION"

# Create directories
mkdir -p "$INSTALL_DIR" "$CONFIG_DIR"

# Install via pip
echo "==> Installing opscentral-agent package..."
pip3 install --quiet opscentral-agent 2>/dev/null || {
    echo "==> pip install failed, trying from source..."
    # Fallback: clone and install
}

# Create config
cat > "$CONFIG_DIR/agent.yml" << EOF
server_url: $SERVER_URL
api_key: $API_KEY
collect_interval: 60
inventory_interval: 300
log_level: INFO
EOF

chmod 600 "$CONFIG_DIR/agent.yml"

# Create systemd service
cat > /etc/systemd/system/opscentral-agent.service << EOF
[Unit]
Description=OpsCentral Monitoring Agent
After=network.target

[Service]
Type=simple
ExecStart=$(command -v opscentral-agent || echo "/usr/local/bin/opscentral-agent")
Restart=always
RestartSec=10
Environment=OC_API_KEY=$API_KEY
Environment=OC_SERVER_URL=$SERVER_URL

[Install]
WantedBy=multi-user.target
EOF

# Enable and start
systemctl daemon-reload
systemctl enable opscentral-agent
systemctl start opscentral-agent

echo ""
echo "==> OpsCentral Agent installed successfully!"
echo "    Config: $CONFIG_DIR/agent.yml"
echo "    Service: systemctl status opscentral-agent"
echo "    Logs: journalctl -u opscentral-agent -f"
