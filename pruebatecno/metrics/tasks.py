#Tareas relacionadas con la captura de métricas del sistema y su almacenamiento en InfluxDB

from celery import shared_task
from celery.utils.log import get_task_logger
from pruebatecno.core.system_info import build_system_payload
from metrics.influxdb import write_pc_metrics

logger = get_task_logger(__name__)

@shared_task(
        bind=True, 
        name="metrics.tasks.capturar_metricas_sistema"
        )
def capturar_metricas_sistema(self):
    payload = build_system_payload()
    cpu_percent = payload.get("cpu_percent")
    memory_percent = payload.get("memory_percent")

    write_pc_metrics(cpu_percent, memory_percent)

    logger.info("Métricas capturadas: CPU=%.2f%%, RAM=%.2f%%", cpu_percent, memory_percent) 
    return {"status": "success", "cpu_percent": cpu_percent, "memory_percent": memory_percent}  



