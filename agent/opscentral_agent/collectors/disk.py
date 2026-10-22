import platform

import psutil


def collect_disk() -> list[dict]:
    metrics = []
    partitions = psutil.disk_partitions()

    for part in partitions:
        try:
            # Skip special filesystems on Linux
            if platform.system() != "Windows" and part.fstype in ("squashfs", "tmpfs", "devtmpfs"):
                continue

            usage = psutil.disk_usage(part.mountpoint)
            metrics.append(
                {
                    "name": "disk_percent",
                    "value": usage.percent,
                    "unit": "%",
                    "tags": {"mountpoint": part.mountpoint, "device": part.device},
                }
            )
            metrics.append(
                {
                    "name": "disk_used_gb",
                    "value": round(usage.used / (1024**3), 2),
                    "unit": "GB",
                    "tags": {"mountpoint": part.mountpoint},
                }
            )
            metrics.append(
                {
                    "name": "disk_total_gb",
                    "value": round(usage.total / (1024**3), 2),
                    "unit": "GB",
                    "tags": {"mountpoint": part.mountpoint},
                }
            )
        except (PermissionError, OSError):
            continue

    # Disk I/O
    try:
        io = psutil.disk_io_counters()
        if io:
            metrics.append(
                {"name": "disk_read_mb", "value": round(io.read_bytes / (1024**2), 2), "unit": "MB"}
            )
            metrics.append(
                {
                    "name": "disk_write_mb",
                    "value": round(io.write_bytes / (1024**2), 2),
                    "unit": "MB",
                }
            )
    except Exception:
        pass

    return metrics
