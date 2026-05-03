from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings


def create_engine_from_settings() -> Engine:
    """根据配置创建数据库引擎。"""
    settings = get_settings()
    return create_engine(settings.database_url, future=True, pool_pre_ping=True)


engine = create_engine_from_settings()
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)
