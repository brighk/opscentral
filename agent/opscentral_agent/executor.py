import logging
import platform
import subprocess
import sys

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes remote actions on the agent host."""

    def execute(self, action_type: str, parameters: dict | None = None) -> dict:
        parameters = parameters or {}
        handler = getattr(self, f"_handle_{action_type}", None)
        if not handler:
            return {"status": "failed", "error": f"Unknown action type: {action_type}"}

        try:
            result = handler(parameters)
            return {"status": "completed", "result": result}
        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _handle_restart_service(self, params: dict) -> dict:
        service_name = params.get("service_name")
        if not service_name:
            raise ValueError("service_name is required")

        if platform.system() == "Windows":
            cmd = ["sc", "restart", service_name]
        else:
            cmd = ["sudo", "systemctl", "restart", service_name]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return {
            "service": service_name,
            "returncode": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
        }

    def _handle_collect_diagnostics(self, params: dict) -> dict:
        diagnostics = {}

        # System info
        diagnostics["platform"] = platform.platform()
        diagnostics["python"] = sys.version

        # Disk usage
        try:
            import shutil
            total, used, free = shutil.disk_usage("/")
            diagnostics["disk"] = {
                "total_gb": round(total / (1024**3), 1),
                "used_gb": round(used / (1024**3), 1),
                "free_gb": round(free / (1024**3), 1),
            }
        except Exception:
            pass

        # Uptime
        try:
            if platform.system() != "Windows":
                result = subprocess.run(["uptime"], capture_output=True, text=True, timeout=10)
                diagnostics["uptime"] = result.stdout.strip()
        except Exception:
            pass

        return diagnostics

    def _handle_update_agent(self, params: dict) -> dict:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "opscentral-agent"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:2000],
        }

    def _handle_health_check(self, params: dict) -> dict:
        import os

        checks = {}

        # CPU
        try:
            import psutil
            checks["cpu_percent"] = psutil.cpu_percent(interval=1)
            checks["memory_percent"] = psutil.virtual_memory().percent
            checks["disk_percent"] = psutil.disk_usage("/").percent
        except ImportError:
            checks["error"] = "psutil not available"

        # Network connectivity
        try:
            import socket
            s = socket.create_connection(("8.8.8.8", 53), timeout=5)
            s.close()
            checks["network"] = "ok"
        except Exception:
            checks["network"] = "unreachable"

        checks["pid"] = os.getpid()
        return checks

    def _handle_custom_script(self, params: dict) -> dict:
        script = params.get("script")
        if not script:
            raise ValueError("script is required")

        timeout = min(params.get("timeout", 60), 300)

        if platform.system() == "Windows":
            cmd = ["powershell", "-Command", script]
        else:
            cmd = ["bash", "-c", script]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
        }
