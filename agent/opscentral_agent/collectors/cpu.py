import platform

import psutil


def collect_cpu() -> list[dict]:
    metrics = []
    cpu_percent = psutil.cpu_percent(interval=1)
    metrics.append({"name": "cpu_percent", "value": cpu_percent, "unit": "%"})

    cpu_freq = psutil.cpu_freq()
    if cpu_freq:
        metrics.append({"name": "cpu_freq_mhz", "value": cpu_freq.current, "unit": "MHz"})

    # getloadavg() is not available on Windows
    if platform.system() != "Windows":
        try:
            load = psutil.getloadavg()
            metrics.append({"name": "load_avg_1m", "value": load[0], "unit": ""})
            metrics.append({"name": "load_avg_5m", "value": load[1], "unit": ""})
            metrics.append({"name": "load_avg_15m", "value": load[2], "unit": ""})
        except (AttributeError, OSError):
            pass

    # Per-CPU usage (works on all platforms)
    metrics.append(
        {"name": "cpu_count_logical", "value": psutil.cpu_count(logical=True), "unit": ""}
    )
    metrics.append(
        {"name": "cpu_count_physical", "value": psutil.cpu_count(logical=False) or 0, "unit": ""}
    )

    return metrics
