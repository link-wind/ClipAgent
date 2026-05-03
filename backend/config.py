import os
from dataclasses import dataclass
from functools import lru_cache


DEFAULT_DATABASE_URL = "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


@dataclass(frozen=True)
class Settings:
    # 数据库连接
    database_url: str
    # Redis 连接
    redis_url: str
    # Celery Broker
    celery_broker_url: str
    # Celery 结果后端
    celery_result_backend: str
    # Celery 队列名
    celery_queue: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    redis_url = os.getenv("CLIPFORGE_REDIS_URL") or os.getenv("REDIS_URL") or DEFAULT_REDIS_URL
    database_url = (
        os.getenv("CLIPFORGE_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL
    )

    return Settings(
        database_url=database_url,
        redis_url=redis_url,
        celery_broker_url=os.getenv("CELERY_BROKER_URL", redis_url),
        celery_result_backend=os.getenv("CELERY_RESULT_BACKEND", redis_url),
        celery_queue=os.getenv("CLIPFORGE_CELERY_QUEUE", "clipforge-agent"),
    )
