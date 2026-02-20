# OpsCentral Agent Installer for Windows
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1 -ApiKey YOUR_KEY -ServerUrl https://your-server.com

param(
    [Parameter(Mandatory=$true)]
    [string]$ApiKey,

    [Parameter(Mandatory=$true)]
    [string]$ServerUrl
)

$ErrorActionPreference = "Stop"
$ConfigDir = "C:\ProgramData\OpsCentral"
$ServiceName = "OpsCentralAgent"

Write-Host "==> Installing OpsCentral Agent..." -ForegroundColor Cyan

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "==> Found $pythonVersion"
} catch {
    Write-Host "Error: Python 3 is required but not found in PATH." -ForegroundColor Red
    Write-Host "Download from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

# Install the agent package
Write-Host "==> Installing opscentral-agent package..."
pip install opscentral-agent --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "==> pip install from PyPI failed, trying local install..." -ForegroundColor Yellow
}

# Create config directory
if (-not (Test-Path $ConfigDir)) {
    New-Item -ItemType Directory -Path $ConfigDir -Force | Out-Null
}

# Write config file
$configContent = @"
server_url: $ServerUrl
api_key: $ApiKey
collect_interval: 60
inventory_interval: 300
log_level: INFO
"@

Set-Content -Path "$ConfigDir\agent.yml" -Value $configContent
Write-Host "==> Config written to $ConfigDir\agent.yml"

# Create a Windows service using NSSM or sc.exe
# For simplicity, we'll create a scheduled task that runs at startup
$agentPath = (Get-Command opscentral-agent -ErrorAction SilentlyContinue).Source
if (-not $agentPath) {
    $agentPath = "python -m opscentral_agent.main"
}

# Remove existing task if present
schtasks /Delete /TN $ServiceName /F 2>$null

# Create scheduled task to run at system startup
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c set OC_API_KEY=$ApiKey && set OC_SERVER_URL=$ServerUrl && $agentPath"
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $ServiceName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null

# Start it now
Start-ScheduledTask -TaskName $ServiceName

Write-Host ""
Write-Host "==> OpsCentral Agent installed successfully!" -ForegroundColor Green
Write-Host "    Config: $ConfigDir\agent.yml"
Write-Host "    Task: schtasks /Query /TN $ServiceName"
Write-Host "    To stop: Stop-ScheduledTask -TaskName $ServiceName"
Write-Host "    To uninstall: Unregister-ScheduledTask -TaskName $ServiceName"
