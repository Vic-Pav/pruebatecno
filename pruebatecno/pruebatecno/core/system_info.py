from typing import Dict
import psutil


def build_system_payload() -> Dict:
    """Construye el payload de métricas del sistema para la API."""
    cpu = float(psutil.cpu_percent())
    mem = float(psutil.virtual_memory().percent)
    return {
        "cpu_percent": cpu,
        "memory_percent": mem,
    }