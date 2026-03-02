"""
Comando para crear las tareas por defecto en la base de datos

"""

from django.core.management.base import BaseCommand
from pruebatecno.pruebatecno.celery.tareas_programadas import populate_beat_schedule
"""
Comando para crear las tareas por defecto en la base de datos

"""

from django.core.management.base import BaseCommand
from pruebatecno.pruebatecno.celery.tareas_programadas import populate_beat_schedule

class Command(BaseCommand):
    help = 'Crea las tareas periódicas por defecto en la base de datos para Celery Beat'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Tareas periódicas por defecto creadas o verificadas exitosamente.'))

        populate_beat_schedule()

        self.stdout.write(self.style.SUCCESS('Tareas periódicas por defecto creadas o verificadas exitosamente.'))
        self.stdout.write(
            self.style.SUCCESS(
                'Puedes revisar y administrar las tareas periódicas desde el panel de administración de Django.'
            )
        )
class Command(BaseCommand):
    help = 'Crea las tareas periódicas por defecto en la base de datos para Celery Beat'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Tareas periódicas por defecto creadas o verificadas exitosamente.'))

        populate_beat_schedule()

        self.stdout.write(self.style.SUCCESS('Tareas periódicas por defecto creadas o verificadas exitosamente.'))
        self.stdout.write(
            self.style.SUCCESS(
                'Puedes revisar y administrar las tareas periódicas desde el panel de administración de Django.'
            )
        )