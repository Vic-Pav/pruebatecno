import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import Alert

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Alert)
def sync_prometheus_on_alert_save(sender, instance: Alert, created, **kwargs):
    """
    Cada vez que se crea/actualiza una Alert en BD:
    - regenerar solo esa alerta en el YAML
    - recargar Prometheus (la función ya lo hace)
    """
    try:
        from pruebatecno.monitoring.prometheus import generate_alert_rules
        generate_alert_rules(alert_id=instance.id)
    except Exception:
        logger.exception("Failed to sync Prometheus rules after saving Alert id=%s", instance.id)


@receiver(post_delete, sender=Alert)
def sync_prometheus_on_alert_delete(sender, instance: Alert, **kwargs):
    """
    En delete NO podemos usar generate_alert_rules(alert_id=...) porque el Alert ya no existe
    y la función no sabe qué nombre borrar.
    Entonces:
    - borrar la regla del YAML por nombre
    - recargar Prometheus (delete_rule ya lo hace)
    """
    try:
        from pruebatecno.monitoring.prometheus import delete_rule
        delete_rule(instance.name)
    except Exception:
        logger.exception("Failed to delete Prometheus rule after deleting Alert name=%s", instance.name)