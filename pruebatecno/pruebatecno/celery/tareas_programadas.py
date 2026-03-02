from celery.schedules import crontab

from pruebatecno.pruebatecno.settings import CELERY_BEAT_SCHEDULE

# TAREAS DE EJEMPLO POR DEFECTO


def get_beat_scheduler():
    """
    Función para obtener la configuración de tareas periódicas. Permite personalización dinámica.
    """
    from django.conf import settings

    # Permitir que las tareas periódicas se definan en settings.py o usar el default
    beat_schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", CELERY_BEAT_SCHEDULE)

    return beat_schedule

def populate_beat_schedule():
    """
    Función para poblar el beat_schedule de Celery con las tareas periódicas definidas.
    Se llama al iniciar el worker para asegurar que las tareas estén registradas.
    """
    from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
    from datetime import timedelta

    print("Creando tareas por defecto en la BBDD...")

    #revisar la sincronizacion de prometheus
    schedule_5min, _ = IntervalSchedule.objects.get_or_create(
        every=5, 
        period=IntervalSchedule.MINUTES,
        )
    
    PeriodicTask.objects.get_or_create(
        name="comprobar sincronizacion de prometheus cada 5 minutos",
        defaults={
            "task": "pruebatecno.tasks.comprobar_sincronizacion",
            "interval": schedule_5min,
            "queue": "low_priority",
            "enabled": True,
        },
    )
    print("creada tarea de comprobación prometheus")

    schedule_5min, _ = IntervalSchedule.objects.get_or_create(
        every=5,
        period=IntervalSchedule.MINUTES,
        )

    PeriodicTask.objects.get_or_create(
        name="recargar reglas de prometheus cada 5 minutos",
        defaults={
            "task": "pruebatecno.tasks.recargar_reglas_prometheus",
            "interval": schedule_5min,
            "queue": "low_priority",
            "enabled": True,
        },
    )
    print("creada tarea de recarga de reglas prometheus")

    #comprobar integridad de alertas cada dia
    schedule_daily_midnight, _ = CrontabSchedule.objects.get_or_create(
        minute=0,
        hour=0,
    )
    PeriodicTask.objects.get_or_create(
        name="validar integridad de las alertas cada dia",
        defaults={
            "task": "pruebatecno.tasks.validar_integridad_alertas",
            "crontab": schedule_daily_midnight,
            "queue": "low_priority",
            "enabled": True,
        },
    )
    print("creada tarea de validación de integridad de alertas")

    #limpiar resultados de tareas cada dia
    schedule_daily_cleanup, _ = CrontabSchedule.objects.get_or_create(
        minute=0,
        hour=1,
    )
    PeriodicTask.objects.get_or_create(
        name="limpiar resultados de tareas",
        defaults={
            "task": "pruebatecno.tasks.cleanup_task_results",
            "crontab": schedule_daily_cleanup,
            "queue": "low_priority",
            "enabled": True,
        },
    )
    print("creada tarea de limpieza de resultados de tareas")

    print("\nTareas por defecto creadas existosamente.")
    print("Puede administrar estas tareas desde el panel de Django Admin en la sección de Tareas Periódicas (Periodic Tasks).")