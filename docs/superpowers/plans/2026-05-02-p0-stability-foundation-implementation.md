# ClipForge P0 Stability Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 ClipForge 落地 PostgreSQL + Redis + Celery 的稳定执行底盘，并同步补齐前端会话恢复、事件轮询和失败态展示。

**Architecture:** FastAPI 继续作为 API 入口，PostgreSQL 持久化 session / message / plan / job / event / artifact，Celery worker 独立承担搜索、下载、渲染长任务，前端继续通过轮询读取 session 快照和 event 明细。P0 不把 WebSocket 作为主链路，而是优先保证持久化、一致性和恢复能力。本阶段仅通过 `docker-compose` 托管 PostgreSQL 和 Redis，前端、FastAPI、Celery worker 继续本地运行。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Celery, Next.js, Zustand, unittest

---

## File Structure

### Backend files to create

- `docker-compose.yml`
  - 本地开发用 PostgreSQL + Redis 依赖编排。
- `.env.example`
  - 提供数据库、Redis、Celery 基础环境变量样例。
- `backend/config.py`
  - 统一读取数据库、Redis、Celery、存储路径等配置。
- `backend/db/__init__.py`
  - 暴露数据库入口。
- `backend/db/base.py`
  - SQLAlchemy Base。
- `backend/db/session.py`
  - 数据库 engine 和 session factory。
- `backend/db/models.py`
  - 六张核心表的 SQLAlchemy 模型。
- `backend/db/repositories/__init__.py`
- `backend/db/repositories/agent_sessions.py`
- `backend/db/repositories/agent_messages.py`
- `backend/db/repositories/agent_plans.py`
- `backend/db/repositories/agent_jobs.py`
- `backend/db/repositories/agent_events.py`
- `backend/db/repositories/agent_artifacts.py`
  - 各表 CRUD。
- `backend/services/agent_session_service.py`
  - 管 session / message / plan 聚合读写。
- `backend/services/agent_execution_service.py`
  - 管 confirm、job 创建、执行编排。
- `backend/services/agent_progress_service.py`
  - 管 event 记录和 session 聚合状态更新。
- `backend/services/agent_read_service.py`
  - 聚合读取 session + plan + clips + events 给 API。
- `backend/tasks/__init__.py`
- `backend/tasks/celery_app.py`
  - Celery app 初始化。
- `backend/tasks/agent_tasks.py`
  - `run_agent_job(job_id)` 任务定义。
- `backend/alembic.ini`
- `backend/alembic/env.py`
- `backend/alembic/script.py.mako`
- `backend/alembic/versions/<timestamp>_create_agent_tables.py`
  - migration。
- `tests/test_agent_persistence.py`
  - session / message / plan / event / artifact 仓储和 service 测试。
- `tests/test_agent_jobs.py`
  - confirm / job / Celery 任务编排测试。
- `tests/test_agent_api_p0.py`
  - API 读写与恢复行为测试。

### Backend files to modify

- `README.md`
  - 增加 `docker-compose` 启动 PostgreSQL / Redis、本地启动后端和 worker 的说明。
- `backend/requirements.txt`
  - 增加 SQLAlchemy, psycopg, alembic, celery, redis 等依赖。
- `backend/main.py`
  - 初始化配置、数据库、静态目录，挂载新 API 行为。
- `backend/api/agent.py`
  - 改成调用新 service，并新增 `GET /sessions/{id}/events`。
- `backend/models/agent.py`
  - Pydantic schema 扩展出 queued / events / artifacts 所需字段。
- `backend/services/agent_service.py`
  - 逐步下线旧内存逻辑，最后可删或转成兼容层。
- `backend/services/search_service.py`
  - 让下载结果更适配 artifact 持久化。
- `backend/services/render_service.py`
  - 让渲染输出更适配 artifact / event 持久化。

### Frontend files to modify

- `src/lib/agentApi.ts`
  - 增加 `getAgentSessionEvents`、更新 session 类型。
- `src/stores/useAgentStore.ts`
  - 增加 activeSessionId、events、恢复与轮询控制。
- `src/components/agent/AgentWorkspace.tsx`
  - 补会话恢复和轮询策略。
- `src/components/agent/AgentChat.tsx`
  - 结合新的恢复行为处理 session 丢失和失败态。
- `src/components/agent/ProgressPanel.tsx`
  - 展示 event 明细或最近执行过程。
- `src/components/agent/ResultPanel.tsx`
  - 适配 artifact / videoUrl 新来源。
- `tests/test_agent_backend.py`
  - 保留并迁移现有行为测试，适配新实现。

---

### Task 1: Add backend infrastructure dependencies and config

**Files:**
- Create: `backend/config.py`
- Create: `.env.example`
- Modify: `backend/requirements.txt`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import unittest


class ConfigTests(unittest.TestCase):
    def test_database_and_celery_settings_can_be_loaded(self):
        os.environ["CLIPFORGE_DATABASE_URL"] = "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge"
        os.environ["CLIPFORGE_REDIS_URL"] = "redis://localhost:6379/0"

        from backend.config import get_settings

        settings = get_settings()

        self.assertEqual(
            settings.database_url,
            "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge",
        )
        self.assertEqual(settings.redis_url, "redis://localhost:6379/0")
        self.assertEqual(settings.celery_broker_url, "redis://localhost:6379/0")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.ConfigTests.test_database_and_celery_settings_can_be_loaded -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.config'`

- [ ] **Step 3: Write minimal implementation**

`backend/requirements.txt`

```text
fastapi==0.110.0
uvicorn[standard]==0.27.1
openai==1.12.0
yt-dlp>=2026.3.17
yt-dlp-ejs>=0.3.1
curl-cffi>=0.13.0
ffmpeg-python==0.2.0
websockets==12.0
python-multipart==0.0.9
pydantic==2.6.1
aiofiles==23.2.1
sqlalchemy==2.0.41
alembic==1.16.1
psycopg[binary]==3.2.9
celery==5.5.2
redis==6.1.0
```

`backend/config.py`

```python
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    celery_broker_url: str
    celery_result_backend: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    database_url = os.getenv(
        "CLIPFORGE_DATABASE_URL",
        "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge",
    )
    redis_url = os.getenv("CLIPFORGE_REDIS_URL", "redis://localhost:6379/0")
    return Settings(
        database_url=database_url,
        redis_url=redis_url,
        celery_broker_url=redis_url,
        celery_result_backend=redis_url,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.ConfigTests.test_database_and_celery_settings_can_be_loaded -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py backend/requirements.txt tests/test_agent_persistence.py
git commit -m "chore: add p0 backend infrastructure config"
```

`.env.example`

```dotenv
CLIPFORGE_DATABASE_URL=postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge
CLIPFORGE_REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

更新提交命令：

```bash
git add .env.example backend/config.py backend/requirements.txt tests/test_agent_persistence.py
git commit -m "chore: add p0 backend infrastructure config"
```

---

### Task 1.5: Add docker-compose for PostgreSQL and Redis

**Files:**
- Create: `docker-compose.yml`
- Modify: `README.md`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import unittest


class DockerComposeContractTests(unittest.TestCase):
    def test_docker_compose_provisions_postgres_and_redis(self):
        source = Path("docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("postgres", source)
        self.assertIn("redis", source)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0.DockerComposeContractTests.test_docker_compose_provisions_postgres_and_redis -v`  
Expected: FAIL because `docker-compose.yml` does not exist

- [ ] **Step 3: Write minimal implementation**

`docker-compose.yml`

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: clipforge
      POSTGRES_USER: clipforge
      POSTGRES_PASSWORD: clipforge
    ports:
      - "5432:5432"
    volumes:
      - clipforge-postgres-data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - clipforge-redis-data:/data

volumes:
  clipforge-postgres-data:
  clipforge-redis-data:
```

README 需要补充：

- `docker compose up -d postgres redis`
- 本地启动 FastAPI、Celery worker、Next.js 的命令

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0.DockerComposeContractTests.test_docker_compose_provisions_postgres_and_redis -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml README.md tests/test_agent_api_p0.py
git commit -m "chore: add local docker compose for postgres and redis"
```

---

### Task 2: Add SQLAlchemy base and database session management

**Files:**
- Create: `backend/db/__init__.py`
- Create: `backend/db/base.py`
- Create: `backend/db/session.py`
- Modify: `backend/main.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class DatabaseSessionTests(unittest.TestCase):
    def test_session_factory_is_exposed(self):
        from backend.db.session import SessionLocal, create_engine_from_settings

        self.assertTrue(callable(SessionLocal))
        self.assertTrue(callable(create_engine_from_settings))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.DatabaseSessionTests.test_session_factory_is_exposed -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.db'`

- [ ] **Step 3: Write minimal implementation**

`backend/db/base.py`

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

`backend/db/session.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings


def create_engine_from_settings():
    settings = get_settings()
    return create_engine(settings.database_url, future=True, pool_pre_ping=True)


engine = create_engine_from_settings()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
```

`backend/db/__init__.py`

```python
from backend.db.base import Base
from backend.db.session import SessionLocal, engine

__all__ = ["Base", "SessionLocal", "engine"]
```

`backend/main.py` 增加导入但先不启用复杂逻辑：

```python
from backend.db import engine
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.DatabaseSessionTests.test_session_factory_is_exposed -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/__init__.py backend/db/base.py backend/db/session.py backend/main.py tests/test_agent_persistence.py
git commit -m "feat: add sqlalchemy database session setup"
```

---

### Task 3: Add SQLAlchemy models for sessions, messages, plans, jobs, events, and artifacts

**Files:**
- Create: `backend/db/models.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class ModelMetadataTests(unittest.TestCase):
    def test_agent_tables_are_registered(self):
        from backend.db.models import AgentSessionRecord, AgentMessageRecord, AgentPlanRecord

        table_names = {
            AgentSessionRecord.__tablename__,
            AgentMessageRecord.__tablename__,
            AgentPlanRecord.__tablename__,
        }

        self.assertEqual(
            table_names,
            {"agent_sessions", "agent_messages", "agent_plans"},
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.ModelMetadataTests.test_agent_tables_are_registered -v`  
Expected: FAIL with `ImportError` for missing model classes

- [ ] **Step 3: Write minimal implementation**

`backend/db/models.py`

```python
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


def _uuid() -> str:
    return str(uuid4())


def _utcnow() -> datetime:
    return datetime.utcnow()


class AgentSessionRecord(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="idle")
    current_step: Mapped[str] = mapped_column(Text, nullable=False, default="")
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_retryable_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class AgentMessageRecord(Base):
    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("agent_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


class AgentPlanRecord(Base):
    __tablename__ = "agent_plans"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("agent_sessions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    target_duration: Mapped[float] = mapped_column(Float, nullable=False, default=30.0)
    style: Mapped[str] = mapped_column(Text, nullable=False, default="cinematic")
    plan_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


class AgentJobRecord(Base):
    __tablename__ = "agent_jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("agent_sessions.id"), nullable=False)
    plan_id: Mapped[str] = mapped_column(ForeignKey("agent_plans.id"), nullable=False)
    job_type: Mapped[str] = mapped_column(Text, nullable=False, default="generate_video")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_step: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class AgentEventRecord(Base):
    __tablename__ = "agent_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("agent_sessions.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("agent_jobs.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    step: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


class AgentArtifactRecord(Base):
    __tablename__ = "agent_artifacts"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("agent_sessions.id"), nullable=False)
    job_id: Mapped[str] = mapped_column(ForeignKey("agent_jobs.id"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    scene_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)
    public_url: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.ModelMetadataTests.test_agent_tables_are_registered -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/models.py tests/test_agent_persistence.py
git commit -m "feat: add p0 agent database models"
```

---

### Task 4: Add Alembic setup and initial database migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/20260502_create_agent_tables.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path
import unittest


class MigrationFilesTests(unittest.TestCase):
    def test_initial_migration_files_exist(self):
        expected = [
            Path("backend/alembic.ini"),
            Path("backend/alembic/env.py"),
        ]
        for path in expected:
            self.assertTrue(path.exists(), f"missing {path}")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.MigrationFilesTests.test_initial_migration_files_exist -v`  
Expected: FAIL because files do not exist

- [ ] **Step 3: Write minimal implementation**

Create Alembic bootstrap files plus a first migration that creates:

- `agent_sessions`
- `agent_messages`
- `agent_plans`
- `agent_jobs`
- `agent_events`
- `agent_artifacts`

Migration should also create indexes:

- `idx_agent_messages_session_id_created_at`
- `idx_agent_plans_session_id_version`
- `idx_agent_jobs_session_id_created_at`
- `idx_agent_jobs_status_created_at`
- `idx_agent_events_session_id_created_at`
- `idx_agent_events_job_id_created_at`
- `idx_agent_artifacts_session_id_created_at`
- `idx_agent_artifacts_job_id_artifact_type`

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.MigrationFilesTests.test_initial_migration_files_exist -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/alembic.ini backend/alembic tests/test_agent_persistence.py
git commit -m "feat: add alembic migration for agent tables"
```

---

### Task 5: Add repositories for sessions, messages, plans, jobs, events, and artifacts

**Files:**
- Create: `backend/db/repositories/__init__.py`
- Create: `backend/db/repositories/agent_sessions.py`
- Create: `backend/db/repositories/agent_messages.py`
- Create: `backend/db/repositories/agent_plans.py`
- Create: `backend/db/repositories/agent_jobs.py`
- Create: `backend/db/repositories/agent_events.py`
- Create: `backend/db/repositories/agent_artifacts.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class RepositoryImportTests(unittest.TestCase):
    def test_session_repository_exposes_create_and_get(self):
        from backend.db.repositories.agent_sessions import AgentSessionRepository

        self.assertTrue(hasattr(AgentSessionRepository, "create"))
        self.assertTrue(hasattr(AgentSessionRepository, "get"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.RepositoryImportTests.test_session_repository_exposes_create_and_get -v`  
Expected: FAIL with missing repository module

- [ ] **Step 3: Write minimal implementation**

Each repository should be a small class around a SQLAlchemy session. Example for session repository:

```python
from backend.db.models import AgentSessionRecord


class AgentSessionRepository:
    def __init__(self, db):
        self.db = db

    def create(self, **kwargs):
        record = AgentSessionRecord(**kwargs)
        self.db.add(record)
        self.db.flush()
        return record

    def get(self, session_id: str):
        return self.db.get(AgentSessionRecord, session_id)
```

Other repositories should expose the minimal methods needed by P0:

- message: `create`, `list_for_session`
- plan: `create`, `get_latest_for_session`, `get`
- job: `create`, `get`, `update_status`
- event: `create`, `list_for_session`
- artifact: `create`, `list_for_session`

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.RepositoryImportTests.test_session_repository_exposes_create_and_get -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/db/repositories tests/test_agent_persistence.py
git commit -m "feat: add agent repositories"
```

---

### Task 6: Add session read/write services backed by PostgreSQL

**Files:**
- Create: `backend/services/agent_session_service.py`
- Create: `backend/services/agent_read_service.py`
- Modify: `backend/models/agent.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class SessionServiceContractTests(unittest.TestCase):
    def test_session_service_exposes_create_get_and_add_message(self):
        from backend.services.agent_session_service import AgentSessionService

        self.assertTrue(hasattr(AgentSessionService, "create_session"))
        self.assertTrue(hasattr(AgentSessionService, "get_session"))
        self.assertTrue(hasattr(AgentSessionService, "add_user_message"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.SessionServiceContractTests.test_session_service_exposes_create_get_and_add_message -v`  
Expected: FAIL with missing service module

- [ ] **Step 3: Write minimal implementation**

`agent_session_service.py` should:

- create session row
- create message row
- create plan row when prompt exists
- update session aggregate fields (`status`, `current_step`, `progress`, `title`)

`agent_read_service.py` should:

- read session
- load latest plan
- load artifacts
- map DB rows back to current Pydantic `AgentSession`

`backend/models/agent.py` should extend API schema with:

- `events: List[AgentEvent] = []`
- `activeJobId: Optional[str]`

plus new `AgentEvent` Pydantic model.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_persistence.SessionServiceContractTests.test_session_service_exposes_create_get_and_add_message -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_session_service.py backend/services/agent_read_service.py backend/models/agent.py tests/test_agent_persistence.py
git commit -m "feat: persist agent sessions and plans"
```

---

### Task 7: Switch agent API read/write endpoints from in-memory storage to database services

**Files:**
- Modify: `backend/api/agent.py`
- Modify: `backend/services/agent_service.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class AgentApiP0ContractTests(unittest.TestCase):
    def test_agent_api_still_exposes_confirm_endpoint(self):
        from backend.api.agent import router

        paths = {route.path for route in router.routes}
        self.assertIn("/sessions/{session_id}/confirm", paths)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_api_still_exposes_confirm_endpoint -v`  
Expected: PASS now, then extend the same test file with DB-backed create/get flow and observe FAIL before implementing

- [ ] **Step 3: Write minimal implementation**

Replace direct access to the global in-memory service with:

- `session_service.create_session`
- `session_service.get_session`
- `session_service.add_user_message`
- `read_service.build_session_response`

Keep `backend/services/agent_service.py` temporarily as compatibility wrapper or remove its storage responsibility entirely. Its only remaining role should be execution orchestration until Task 9.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0 -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/agent.py backend/services/agent_service.py tests/test_agent_api_p0.py
git commit -m "refactor: route agent api through database services"
```

---

### Task 8: Add Celery app and Redis-backed job execution entrypoint

**Files:**
- Create: `backend/tasks/__init__.py`
- Create: `backend/tasks/celery_app.py`
- Create: `backend/tasks/agent_tasks.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class CeleryContractTests(unittest.TestCase):
    def test_agent_task_entrypoint_exists(self):
        from backend.tasks.agent_tasks import run_agent_job

        self.assertTrue(callable(run_agent_job))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.CeleryContractTests.test_agent_task_entrypoint_exists -v`  
Expected: FAIL because task module does not exist

- [ ] **Step 3: Write minimal implementation**

`backend/tasks/celery_app.py`

```python
from celery import Celery

from backend.config import get_settings


settings = get_settings()
celery_app = Celery(
    "clipforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.task_default_queue = "clipforge-agent"
```

`backend/tasks/agent_tasks.py`

```python
from backend.tasks.celery_app import celery_app


@celery_app.task(name="backend.tasks.agent_tasks.run_agent_job")
def run_agent_job(job_id: str) -> None:
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.CeleryContractTests.test_agent_task_entrypoint_exists -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tasks tests/test_agent_jobs.py
git commit -m "feat: add celery task entrypoint for agent jobs"
```

---

### Task 9: Add execution service that creates jobs and uses Celery instead of asyncio.create_task

**Files:**
- Create: `backend/services/agent_execution_service.py`
- Modify: `backend/api/agent.py`
- Modify: `backend/services/agent_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class ConfirmFlowContractTests(unittest.TestCase):
    def test_execution_service_exposes_confirm_session(self):
        from backend.services.agent_execution_service import AgentExecutionService

        self.assertTrue(hasattr(AgentExecutionService, "confirm_session"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ConfirmFlowContractTests.test_execution_service_exposes_confirm_session -v`  
Expected: FAIL with missing service

- [ ] **Step 3: Write minimal implementation**

`AgentExecutionService.confirm_session(session_id)` should:

1. Load session and latest plan
2. Validate state and plan existence
3. Create `agent_jobs` row with `queued`
4. Update session to:
   - `status = queued`
   - `progress = 25`
   - `current_step = "任务已入队"`
   - `active_job_id = job.id`
5. Write `job_queued` event
6. Dispatch `run_agent_job.delay(job.id)`
7. Return fresh session aggregate

Then update `backend/api/agent.py` to call this service instead of `asyncio.create_task(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_execution_service.py backend/api/agent.py backend/services/agent_service.py tests/test_agent_jobs.py
git commit -m "feat: queue agent confirmation jobs through celery"
```

---

### Task 10: Add progress service and persist job events / aggregate session state during execution

**Files:**
- Create: `backend/services/agent_progress_service.py`
- Modify: `backend/tasks/agent_tasks.py`
- Modify: `backend/services/search_service.py`
- Modify: `backend/services/render_service.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class ProgressServiceContractTests(unittest.TestCase):
    def test_progress_service_exposes_record_event(self):
        from backend.services.agent_progress_service import AgentProgressService

        self.assertTrue(hasattr(AgentProgressService, "record_event"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs.ProgressServiceContractTests.test_progress_service_exposes_record_event -v`  
Expected: FAIL because service does not exist

- [ ] **Step 3: Write minimal implementation**

`AgentProgressService` should provide:

- `record_event(...)`
- `update_session_status(...)`
- `mark_job_running(...)`
- `mark_job_failed(...)`
- `mark_job_succeeded(...)`

`run_agent_job(job_id)` should now:

1. mark job running
2. write `job_started`
3. call search/download
4. write scene events
5. call render
6. create artifacts
7. mark success / failure

`search_service.py` and `render_service.py` should accept event/progress callbacks or be wrapped so they no longer write websocket-first progress as the source of truth.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_jobs -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/agent_progress_service.py backend/tasks/agent_tasks.py backend/services/search_service.py backend/services/render_service.py tests/test_agent_jobs.py
git commit -m "feat: persist agent execution progress and events"
```

---

### Task 11: Add event and artifact query endpoints for frontend recovery

**Files:**
- Modify: `backend/api/agent.py`
- Modify: `backend/models/agent.py`
- Modify: `backend/services/agent_read_service.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Write the failing test**

```python
import unittest


class EventRouteContractTests(unittest.TestCase):
    def test_event_history_endpoint_is_registered(self):
        from backend.api.agent import router

        paths = {route.path for route in router.routes}
        self.assertIn("/sessions/{session_id}/events", paths)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0.EventRouteContractTests.test_event_history_endpoint_is_registered -v`  
Expected: FAIL because endpoint is missing

- [ ] **Step 3: Write minimal implementation**

Add:

- `GET /api/agent/sessions/{session_id}/events`

Response shape:

```python
class AgentEvent(BaseModel):
    id: str
    eventType: str
    step: str
    progress: float | None = None
    message: str
    payload: dict = Field(default_factory=dict)
    createdAt: str
```

Read service should decode `payload_json` and map rows to this schema.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0 -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/api/agent.py backend/models/agent.py backend/services/agent_read_service.py tests/test_agent_api_p0.py
git commit -m "feat: add agent event history endpoint"
```

---

### Task 12: Update frontend API client and Zustand store for session recovery and event polling

**Files:**
- Modify: `src/lib/agentApi.ts`
- Modify: `src/stores/useAgentStore.ts`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Write the failing test**

Add a frontend contract test to `tests/test_agent_backend.py` that asserts the client surface exposes an events fetcher and the store shape contains `events` plus `activeSessionId`.

```python
def test_frontend_store_supports_recovery_fields(self):
    store_source = Path("src/stores/useAgentStore.ts").read_text(encoding="utf-8")
    self.assertIn("activeSessionId", store_source)
    self.assertIn("events", store_source)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.FrontendClientContractTests.test_frontend_store_supports_recovery_fields -v`  
Expected: FAIL because those fields do not exist

- [ ] **Step 3: Write minimal implementation**

`src/lib/agentApi.ts` should add:

- `getAgentSessionEvents(sessionId: string)`

`src/stores/useAgentStore.ts` should add:

- `activeSessionId`
- `events`
- `setActiveSessionId`
- `setEvents`
- `reset` should clear all recovery fields

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.FrontendClientContractTests.test_frontend_store_supports_recovery_fields -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lib/agentApi.ts src/stores/useAgentStore.ts tests/test_agent_backend.py
git commit -m "feat: add frontend session recovery state"
```

---

### Task 13: Update Agent workspace UI to restore sessions, poll execution states, and show event history / failure states

**Files:**
- Modify: `src/components/agent/AgentWorkspace.tsx`
- Modify: `src/components/agent/AgentChat.tsx`
- Modify: `src/components/agent/ProgressPanel.tsx`
- Modify: `src/components/agent/ResultPanel.tsx`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Write the failing test**

Add UI contract checks for:

- session restore path
- event fetch call
- settled vs running polling split

```python
def test_workspace_polls_running_sessions_and_restores_events(self):
    source = Path("src/components/agent/AgentWorkspace.tsx").read_text(encoding="utf-8")
    self.assertIn("getAgentSessionEvents", source)
    self.assertIn("activeSessionId", source)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_polls_running_sessions_and_restores_events -v`  
Expected: FAIL because those references are missing

- [ ] **Step 3: Write minimal implementation**

`AgentWorkspace.tsx` should:

- restore `activeSessionId`
- load session and events on mount
- poll only when status is `queued/searching/downloading/rendering`

`AgentChat.tsx` should:

- persist `activeSessionId` after session creation
- distinguish between:
  - missing session
  - failed session
  - temporary polling failure

`ProgressPanel.tsx` should show:

- current step
- progress
- recent events or latest event list

`ResultPanel.tsx` should read final artifact or `videoUrl` from the recovered session.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend.FrontendClientContractTests.test_workspace_polls_running_sessions_and_restores_events -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/components/agent/AgentWorkspace.tsx src/components/agent/AgentChat.tsx src/components/agent/ProgressPanel.tsx src/components/agent/ResultPanel.tsx tests/test_agent_backend.py
git commit -m "feat: restore agent sessions and event history in frontend"
```

---

### Task 14: Update backend startup docs and health checks for PostgreSQL / Redis / Celery development workflow

**Files:**
- Modify: `README.md`
- Modify: `backend/main.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Write the failing test**

Add a backend API contract test that verifies `/health` still exists and README mentions PostgreSQL / Redis / Celery.

```python
import unittest
from pathlib import Path


class DocsContractTests(unittest.TestCase):
    def test_readme_mentions_postgres_redis_and_celery(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        self.assertIn("PostgreSQL", readme)
        self.assertIn("Redis", readme)
        self.assertIn("Celery", readme)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0.DocsContractTests.test_readme_mentions_postgres_redis_and_celery -v`  
Expected: FAIL because README has not been updated

- [ ] **Step 3: Write minimal implementation**

Update README with:

- `docker compose up -d postgres redis`
- PostgreSQL setup
- Redis setup
- Celery worker startup command
- Alembic migration command

Optionally extend `/health` to return database / queue readiness shape later, but keep P0 minimal and backward compatible.

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_api_p0.DocsContractTests.test_readme_mentions_postgres_redis_and_celery -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md backend/main.py tests/test_agent_api_p0.py
git commit -m "docs: add p0 infrastructure startup workflow"
```

---

### Task 15: Run full verification for backend contracts, frontend types, and migration-integrated flows

**Files:**
- Modify: `tests/test_agent_backend.py`
- Modify: `tests/test_agent_persistence.py`
- Modify: `tests/test_agent_jobs.py`
- Modify: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Add or update final verification coverage**

Make sure the test suite covers:

- config loading
- SQLAlchemy model registration
- migration file presence
- repository contract
- session service contract
- Celery task entrypoint
- confirm queueing flow
- event history endpoint
- frontend recovery store shape
- workspace recovery polling shape

- [ ] **Step 2: Run backend unit test suite**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_backend tests.test_agent_persistence tests.test_agent_jobs tests.test_agent_api_p0 -v`  
Expected: PASS

- [ ] **Step 3: Run frontend type check**

Run: `npx tsc --noEmit`  
Expected: PASS

- [ ] **Step 4: Verify no tracked build artifacts were reintroduced**

Run: `git status --short`  
Expected: No staged or unstaged `.next/`, `node_modules/`, or `tsconfig.tsbuildinfo` source-control regressions in the final implementation diff

- [ ] **Step 5: Commit final verification fixes**

```bash
git add tests
git commit -m "test: verify p0 stability foundation flow"
```

---

## Self-Review

### Spec coverage

This plan covers every spec section:

- Backend module boundaries: Tasks 5-10
- Data model: Tasks 3-4
- Celery execution: Tasks 8-10
- Frontend recovery: Tasks 12-13
- Migration path: Tasks 1-15 in the same order as the spec

No spec requirement is left without an implementation task.

### Placeholder scan

The plan avoids `TBD`, `TODO`, “appropriate handling”, and other placeholders. Every task names exact files, expected commands, and concrete outputs.

### Type consistency

The same core names are used throughout:

- `AgentSessionService`
- `AgentExecutionService`
- `AgentProgressService`
- `run_agent_job(job_id)`
- `agent_sessions`, `agent_messages`, `agent_plans`, `agent_jobs`, `agent_events`, `agent_artifacts`

No alternate naming scheme is introduced in later tasks.

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-02-p0-stability-foundation-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
