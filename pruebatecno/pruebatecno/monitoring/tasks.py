from celery import shared_task
from celery.utils.log import get_task_logger
import time

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    name="pruebatecno.tasks.comprobar_sincronizacion",
    max_retries=3,
    default_retry_delay=10, #reintento cada 10 segundos
)
def comprobar_sincronizacion(self, alert_uuid=None):
    "Sincroniza con Prometheus y maneja errores con trys y logs."
    "ARGS: alert_uuid (str): UUID de la alerta a sincronizar. Si es None, se sincronizan todas las alertas."

    try:
        from monitoring.prometheus import generate_alert_rules

        logger.info(f"Inicio de tarea: comprobar_sincronizacion (alert_uuid={alert_uuid})")
        count = generate_alert_rules()
        logger.info(f"Sincronización exitosa. Total de reglas sincronizadas: {count}")

        return {
            "status": "success",
            "rules_count": count,
            "alert_uuid": str(alert_uuid) if alert_uuid else "all"
        }
    except Exception as exc:
        logger.error(f"Error en tarea comprobar_sincronizacion: {exc}", exc_info=True)

        # Reintentar la tarea en caso de error
        raise self.retry(exc=exc)
    
@shared_task(name="pruebatecno.tasks.sincronizacion")
def validar_sincronizacion():
    """
    Verficación de postgres y Prometheus para asegurar que las alertas estén sincronizadas.
    """
    from metrics.models import Alert

    logger.info("Validando integridad de alertas entre PostgreSQL y Prometheus...")
    
    errors = []
    
    for alert in Alert.objects.filter(enabled=True):
        #validar existencia de expresion PromQL
        if not hasattr(alert, 'expr') or not alert.expr.strip() or not alert.expr.strip():
            errors.append(f"Alerta ({alert.name}) no tiene expresión PromQL válida.")
            
        #Validación por nombre
        if not alert.name or len (alert.name) < 3:
            errors.append(f"Alerta ({alert.name}) tiene un nombre inválido.")

    if errors:
        logger.error(f"Errores de integridad encontrados: {len(errors)}. Detalles: {errors}")
    else:
        logger.info("Integridad de alertas validada exitosamente. No se encontraron errores.")

    return {
        "alertas_totales": Alert.objects.filter(enabled=True).count(),
        "errores_encontrados": (errors)
    }

@shared_task(
    bind=True,
    name="pruebatecno.tasks.recargar_reglas_prometheus",
    max_retries=5,
    default_retry_delay= 5, #reintento cada 5 segundos
)   

def recargar_reglas_prometheus(self):
    "Tarea para recargar las reglas de Prometheus. Reintenta en caso de fallo."
    try:
        from monitoring.prometheus import reload_prometheus_rules

        logger.info("Iniciando recarga de reglas en Prometheus...")
        success, message = reload_prometheus_rules()

        if not success:
            raise Exception(f"Error al recargar reglas en Prometheus: {message}")
        
        logger.info("Recarga de reglas en Prometheus exitosa.")
        return {"status": "success", "message": message}
    except Exception as exc:
        logger.error(f"Error en tarea recargar_reglas_prometheus: {exc}")
        raise self.retry(exc=exc)