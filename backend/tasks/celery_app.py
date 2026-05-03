from celery import Celery

from backend.config import get_settings


settings = get_settings()

celery_app = Celery(
    "clipforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_default_queue = "clipforge-agent"
