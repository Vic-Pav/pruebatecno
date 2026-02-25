from .celery_config import app as celery_app
from .app import app as get_beat_scheduler

celery_app.conf.beat_scheduler = get_beat_scheduler()

__all__ = ['celery_app']