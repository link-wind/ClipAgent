from celery import Celery

from backend.config import get_settings


settings = get_settings()

celery_app = Celery(
    "clipforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["backend.tasks.agent_tasks"],
)
celery_app.conf.task_default_queue = "clipforge-agent"

# 显式导入任务，确保 worker 冷启动时完成注册
from backend.tasks import agent_tasks  # noqa: F401,E402
