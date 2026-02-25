import os
from pruebatecno.pruebatecno.celery.celery_config import Celery
from celery.schedules import crontab

#set default de Django Settings para Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pruebatecno.settings')

app = Celery('pruebatecno')

#configuraciones provenientes de settings.py con prefijo CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

#descubrir tareas en las aplicaciones de Django
app.autodiscover_tasks()

@app.task(bind=True, ingnore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
