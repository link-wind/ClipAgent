import os
from dataclasses import dataclass
from functools import lru_cache

from backend.services.runtime_config_service import (
    DEFAULT_DATABASE_URL,
    DEFAULT_REDIS_URL,
    runtime_config_service,
)


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
    # 知识文件存储目录
    knowledge_storage_dir: str
    # 知识 ingestion 队列
    knowledge_queue: str
    # Planner 运行模式
    planner_mode: str
    # Planner 模型名
    planner_model: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    redis_url = runtime_config_service.get_effective_value("CLIPFORGE_REDIS_URL") or DEFAULT_REDIS_URL
    database_url = runtime_config_service.get_effective_value("CLIPFORGE_DATABASE_URL") or DEFAULT_DATABASE_URL

    return Settings(
        database_url=database_url,
        redis_url=redis_url,
        celery_broker_url=runtime_config_service.get_effective_value("CELERY_BROKER_URL") or redis_url,
        celery_result_backend=runtime_config_service.get_effective_value("CELERY_RESULT_BACKEND") or redis_url,
        celery_queue=runtime_config_service.get_effective_value("CLIPFORGE_CELERY_QUEUE") or "clipforge-agent",
        knowledge_storage_dir=runtime_config_service.get_effective_value("CLIPFORGE_KNOWLEDGE_STORAGE_DIR")
        or "backend/storage/knowledge",
        knowledge_queue=runtime_config_service.get_effective_value("CLIPFORGE_KNOWLEDGE_QUEUE")
        or "clipforge-knowledge",
        planner_mode=os.getenv("CLIPFORGE_PLANNER_MODE", "langchain"),
        planner_model=os.getenv("CLIPFORGE_PLANNER_MODEL", "gpt-4o-mini"),
    )
