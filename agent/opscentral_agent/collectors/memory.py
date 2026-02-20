import psutil


def collect_memory() -> list[dict]:
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return [
        {"name": "memory_percent", "value": mem.percent, "unit": "%"},
        {"name": "memory_used_gb", "value": round(mem.used / (1024**3), 2), "unit": "GB"},
        {"name": "memory_available_gb", "value": round(mem.available / (1024**3), 2), "unit": "GB"},
        {"name": "memory_total_gb", "value": round(mem.total / (1024**3), 2), "unit": "GB"},
        {"name": "swap_percent", "value": swap.percent, "unit": "%"},
        {"name": "swap_used_gb", "value": round(swap.used / (1024**3), 2), "unit": "GB"},
    ]
