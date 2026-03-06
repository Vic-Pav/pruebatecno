from django.apps import AppConfig

class MetricsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "metrics"

    def ready(self):
        from django.db.models.signals import post_save, post_delete
        from metrics.models import Alert, AlertCondition
        from django.db import transaction
        from . import signals 

        def schedule_sync_to_prometheus(**kwargs):
            """
            Uso de Celery
            """
            def encolar_tarea():
                from pruebatecno.monitoring.tasks import recargar_reglas_prometheus  # Importar la tarea de Celery dentro de la función para evitar problemas de importación circular
        # ← Importar desde el módulo unificado
                #Extraer UUID de la instancia
                instance = kwargs.get('instance')
                alert_id = None

                if isinstance(instance, Alert):
                    alert_id = instance.id
                elif isinstance(instance, AlertCondition):
                    alert_id = instance.alert.id        
                
                #cola de tarea asincrona
                recargar_reglas_prometheus.delay(alert_uuid=str(alert_id))

            #espera a la finalizacion de la transacción para encolar la tarea, asegurando que los datos estén guardados antes de la sincronización
            transaction.on_commit(encolar_tarea)


        #conectar las señales de guardado y eliminación a la función de programación de tareas para sincronización con Prometheus
        post_save.connect(schedule_sync_to_prometheus, sender=Alert)
        post_save.connect(schedule_sync_to_prometheus, sender=AlertCondition)
        post_delete.connect(schedule_sync_to_prometheus, sender=AlertCondition)
