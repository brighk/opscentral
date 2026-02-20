"""Process collector — top processes by CPU and memory usage."""

import logging
import platform

import psutil

logger = logging.getLogger(__name__)


def collect_processes(top_n: int = 20) -> list[dict]:
    """Collect top processes by CPU and memory usage.

    Returns a list of process dicts with pid, name, cpu_percent, memory_percent,
    memory_mb, status, username, and create_time.
    """
    processes = []
    try:
        # Get all process info in one shot for efficiency
        attrs = [
            "pid", "name", "cpu_percent", "memory_percent",
            "memory_info", "status", "username", "create_time",
            "cmdline", "num_threads",
        ]
        for proc in psutil.process_iter(attrs=attrs):
            try:
                info = proc.info
                memory_mb = 0
                if info.get("memory_info"):
                    memory_mb = round(info["memory_info"].rss / (1024 * 1024), 1)

                cmdline = info.get("cmdline") or []
                command = " ".join(cmdline[:5]) if cmdline else info.get("name", "")

                processes.append({
                    "pid": info["pid"],
                    "name": info.get("name", "unknown"),
                    "cpu_percent": round(info.get("cpu_percent", 0) or 0, 1),
                    "memory_percent": round(info.get("memory_percent", 0) or 0, 1),
                    "memory_mb": memory_mb,
                    "status": info.get("status", "unknown"),
                    "username": info.get("username"),
                    "num_threads": info.get("num_threads", 0),
                    "command": command[:200],  # Truncate long commands
                    "create_time": info.get("create_time"),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Sort by CPU descending, then memory descending
        processes.sort(key=lambda p: (p["cpu_percent"], p["memory_percent"]), reverse=True)
        processes = processes[:top_n]

    except Exception as e:
        logger.error(f"Error collecting processes: {e}")

    return processes


def collect_process_summary() -> list[dict]:
    """Collect summary process metrics as standard metrics format."""
    metrics = []
    try:
        pids = psutil.pids()
        metrics.append({"name": "process_count", "value": len(pids), "unit": "count"})

        # Count by status
        status_counts = {}
        for proc in psutil.process_iter(attrs=["status"]):
            try:
                st = proc.info["status"]
                status_counts[st] = status_counts.get(st, 0) + 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for status, count in status_counts.items():
            metrics.append({
                "name": "process_count_by_status",
                "value": count,
                "unit": "count",
                "tags": {"status": status},
            })
    except Exception as e:
        logger.error(f"Error collecting process summary: {e}")

    return metrics
