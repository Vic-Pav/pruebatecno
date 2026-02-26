import os
from celery import Celery
from celery.schedules import crontab

# set default Django settings module for Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pruebatecno.settings')

# renamed to celery_app and exported for consistent imports
celery_app = Celery('pruebatecno')

# load config from Django settings (CELERY_*)
celery_app.config_from_object('django.conf:settings', namespace='CELERY')

# autodiscover tasks from installed apps
celery_app.autodiscover_tasks()

@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
