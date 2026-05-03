from backend.db import models
from backend.db.base import Base

__all__ = ["Base", "SessionLocal", "create_engine_from_settings", "engine", "models"]


def __getattr__(name):
    # 按需加载数据库运行时对象
    if name in {"SessionLocal", "create_engine_from_settings", "engine"}:
        from backend.db.session import SessionLocal, create_engine_from_settings, engine

        values = {
            "SessionLocal": SessionLocal,
            "create_engine_from_settings": create_engine_from_settings,
            "engine": engine,
        }
        return values[name]
    raise AttributeError(name)
