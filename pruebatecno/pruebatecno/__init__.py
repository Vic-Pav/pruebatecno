from .celery import celery_app

__all__ = ('celery_app',)

# Import monitoring tasks using a package-relative import so it works
# both inside the Docker container and running locally.
from .monitoring import tasks
