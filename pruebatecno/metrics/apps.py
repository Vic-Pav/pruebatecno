from django.apps import AppConfig

class MetricsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "metrics"

    def ready(self):
        from django.db.models.signals import post_save, post_delete
        from metrics.models import Alert, AlertCondition
        from django.db import transaction

        def schedule_sync_to_prometheus(**kwargs):
            """
            Uso de Celery
            """
            def encolar_tarea():
                from monitoring.tasks import recargar_reglas_prometheus
        # ← Importar desde el módulo unificado
                #Extraer UUID de la instancia
                instance = kwargs.get('instance')
                alert_uuid = None

                if isinstance(instance, Alert):
                    alert_uuid = instance.uuid
                elif isinstance(instance, AlertCondition):
                    alert_uuid = instance.alert.uuid        
                
                #cola de tarea asincrona
                recargar_reglas_prometheus.delay(alert_uuid=str(alert_uuid))

            #espera a la finalizacion de la transacción para encolar la tarea, asegurando que los datos estén guardados antes de la sincronización
            transaction.on_commit(encolar_tarea)


        #conectar las señales de guardado y eliminación a la función de programación de tareas para sincronización con Prometheus
        post_save.connect(schedule_sync_to_prometheus, sender=Alert)
        post_save.connect(schedule_sync_to_prometheus, sender=AlertCondition)
        post_delete.connect(schedule_sync_to_prometheus, sender=AlertCondition)
