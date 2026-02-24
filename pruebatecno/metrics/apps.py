from django.apps import AppConfig

class MetricsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "metrics"

    def ready(self):
        from django.db.models.signals import post_save, post_delete
        from metrics.models import Alert, AlertCondition
        
        # ← Importar desde el módulo unificado
        from pruebatecno.monitoring.prometheus import generate_alert_rules

        from django.db import transaction

        def schedule_generate_alert_rules(**kw):
            transaction.on_commit(lambda: generate_alert_rules())

        post_save.connect(schedule_generate_alert_rules, sender=Alert)
        post_save.connect(schedule_generate_alert_rules, sender=AlertCondition)
        post_delete.connect(lambda **kw: transaction.on_commit(lambda: generate_alert_rules()), sender=AlertCondition)
