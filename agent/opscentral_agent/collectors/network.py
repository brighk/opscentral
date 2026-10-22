import psutil


def collect_network() -> list[dict]:
    metrics = []

    net_io = psutil.net_io_counters()
    metrics.append(
        {
            "name": "net_bytes_sent_mb",
            "value": round(net_io.bytes_sent / (1024**2), 2),
            "unit": "MB",
        }
    )
    metrics.append(
        {
            "name": "net_bytes_recv_mb",
            "value": round(net_io.bytes_recv / (1024**2), 2),
            "unit": "MB",
        }
    )
    metrics.append({"name": "net_packets_sent", "value": net_io.packets_sent, "unit": ""})
    metrics.append({"name": "net_packets_recv", "value": net_io.packets_recv, "unit": ""})
    metrics.append({"name": "net_errors_in", "value": net_io.errin, "unit": ""})
    metrics.append({"name": "net_errors_out", "value": net_io.errout, "unit": ""})

    # Connection count
    try:
        connections = psutil.net_connections(kind="inet")
        metrics.append({"name": "net_connections", "value": len(connections), "unit": ""})
    except (psutil.AccessDenied, PermissionError):
        pass

    return metrics
