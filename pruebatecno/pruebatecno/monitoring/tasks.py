from celery import shared_task
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

@shared_task(
    bind=True,
    name="pruebatecno.tasks.comprobar_sincronizacion",
    max_retries=3,
    default_retry_delay=10,
)
def comprobar_sincronizacion(self, alert_uuid=None):
    """
    Reconcilia reglas (total si alert_uuid=None, puntual si viene UUID).
    """
    try:
        from monitoring.prometheus import generate_alert_rules

        logger.info("Inicio comprobar_sincronizacion(alert_uuid=%s)", alert_uuid)
        rules_count = generate_alert_rules(alert_uuid=alert_uuid)  # ahora sí retorna número

        return {
            "status": "success",
            "rules_count": rules_count,
            "alert_uuid": alert_uuid or "all",
        }
    except Exception as exc:
        logger.error("Error en comprobar_sincronizacion: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

@shared_task(
    bind=True,
    name="pruebatecno.tasks.recargar_reglas_prometheus",
    max_retries=5,
    default_retry_delay=5,
)
def recargar_reglas_prometheus(self, alert_uuid=None):
    """
    Update puntual del YAML + reload (si alert_uuid viene) o reconcile total (si no viene).
    Reutiliza la misma función de alto nivel para evitar duplicación.
    """
    try:
        from monitoring.prometheus import generate_alert_rules

        logger.info("Inicio recargar_reglas_prometheus(alert_uuid=%s)", alert_uuid)
        rules_count = generate_alert_rules(alert_uuid=alert_uuid)

        return {"status": "success", "rules_count": rules_count}
    except Exception as exc:
        logger.error("Error en recargar_reglas_prometheus: %s", exc, exc_info=True)
        raise self.retry(exc=exc)

@shared_task(name="pruebatecno.tasks.validar_integridad_alertas")
def validar_integridad_alertas():
    # si quieres, aquí solo renombrar función para que coincida con el task name
    from metrics.models import Alert
    # ... tu lógica ...
    return {"status": "ok"}

