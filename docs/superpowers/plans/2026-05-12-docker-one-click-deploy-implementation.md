# Docker One-Click Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package ClipForge into a single-machine Docker Compose stack that starts frontend, API, worker, PostgreSQL, and Redis with one command.

**Architecture:** Use one backend image for both FastAPI and Celery, one frontend image for Next.js production, and a Compose stack that wires services through Docker DNS names. Keep existing artifact paths (`backend/downloads`, `backend/output`) and mount shared Docker volumes into API and worker.

**Tech Stack:** Docker Compose, Python 3.12 slim, FastAPI/Uvicorn, Celery, PostgreSQL 16, Redis 7, Node LTS, Next.js 14, Alembic, FFmpeg.

---

## File Structure

Create and modify these files:

- Create `Dockerfile.backend`: backend runtime image for API and worker.
- Create `Dockerfile.frontend`: production Next.js runtime image.
- Create `docker/api-entrypoint.sh`: waits for dependencies, runs Alembic migrations, starts Uvicorn.
- Create `docker/worker-entrypoint.sh`: waits for dependencies, starts Celery worker.
- Modify `docker-compose.yml`: expand from infrastructure-only to full app stack.
- Modify `.env.example`: make Compose defaults first-class and preserve local-development guidance.
- Modify `README.md`: document one-click deployment and keep existing local development instructions.
- Create `tests/test_docker_deploy_contract.py`: static deployment contract tests.
- Review `next.config.js`: media rewrites already exist; keep them and cover them with tests instead of changing unless implementation discovers drift.

Do not modify agent planning, provider, worker execution, or render logic in this stage.

---

### Task 1: Add Static Docker Deployment Contract Tests

**Files:**
- Create: `tests/test_docker_deploy_contract.py`

- [ ] **Step 1: Write failing tests for required Docker files**

Create `tests/test_docker_deploy_contract.py` with:

```python
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


class DockerDeployContractTests(unittest.TestCase):
    def test_dockerfiles_and_entrypoints_exist(self) -> None:
        self.assertTrue((ROOT / "Dockerfile.backend").is_file())
        self.assertTrue((ROOT / "Dockerfile.frontend").is_file())
        self.assertTrue((ROOT / "docker/api-entrypoint.sh").is_file())
        self.assertTrue((ROOT / "docker/worker-entrypoint.sh").is_file())
```

- [ ] **Step 2: Write failing tests for Compose services and volumes**

Append:

```python
    def test_compose_defines_full_clipforge_stack(self) -> None:
        compose = read("docker-compose.yml")

        for service in ("postgres:", "redis:", "api:", "worker:", "frontend:"):
            self.assertIn(service, compose)

        self.assertIn("Dockerfile.backend", compose)
        self.assertIn("Dockerfile.frontend", compose)
        self.assertIn("clipforge-downloads:", compose)
        self.assertIn("clipforge-output:", compose)
        self.assertIn("backend/downloads", compose)
        self.assertIn("backend/output", compose)
        self.assertIn("CLIPFORGE_DATABASE_URL", compose)
        self.assertIn("CLIPFORGE_REDIS_URL", compose)
        self.assertIn("CELERY_BROKER_URL", compose)
        self.assertIn("CELERY_RESULT_BACKEND", compose)
        self.assertIn("CLIPFORGE_API_ORIGIN", compose)
        self.assertIn("OPENAI_API_KEY", compose)
        self.assertNotIn("env_file:", compose)
```

- [ ] **Step 3: Write failing tests for entrypoint behavior**

Append:

```python
    def test_backend_entrypoints_run_expected_commands(self) -> None:
        api = read("docker/api-entrypoint.sh")
        worker = read("docker/worker-entrypoint.sh")

        self.assertIn("python -m alembic -c backend/alembic.ini upgrade head", api)
        self.assertIn("python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010", api)
        self.assertIn("python -m celery -A backend.tasks.celery_app:celery_app worker", worker)
        self.assertIn('-Q "${CLIPFORGE_CELERY_QUEUE:-clipforge-agent}"', worker)
```

- [ ] **Step 4: Write failing tests for frontend routing and docs**

Append:

```python
    def test_next_rewrites_include_api_and_media_paths(self) -> None:
        next_config = read("next.config.js")

        self.assertIn("CLIPFORGE_API_ORIGIN", next_config)
        self.assertIn("source: '/api/agent/:path*'", next_config)
        self.assertIn("source: '/downloads/:path*'", next_config)
        self.assertIn("source: '/output/:path*'", next_config)


    def test_env_example_and_readme_document_one_click_deploy(self) -> None:
        env_example = read(".env.example")
        readme = read("README.md")

        self.assertIn("postgres:5432", env_example)
        self.assertIn("redis:6379", env_example)
        self.assertIn("CLIPFORGE_API_ORIGIN=http://api:8010", env_example)
        self.assertIn("docker compose up --build -d", readme)
        self.assertIn("Docker 一键部署", readme)
        self.assertIn("docker compose ps", readme)
```

- [ ] **Step 5: Run tests and verify they fail**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract -v
```

Expected: FAIL because Dockerfiles, entrypoints, Compose services, and docs are not implemented yet. `next.config.js` assertions may already pass.

- [ ] **Step 6: Commit failing tests**

Run:

```bash
git add tests/test_docker_deploy_contract.py
git commit -m "test: add docker deploy contract"
```

---

### Task 2: Add Backend Docker Image And Entrypoints

**Files:**
- Create: `Dockerfile.backend`
- Create: `docker/api-entrypoint.sh`
- Create: `docker/worker-entrypoint.sh`

- [ ] **Step 1: Create backend Dockerfile**

Create `Dockerfile.backend`:

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ffmpeg \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r backend/requirements.txt

COPY backend backend
COPY fixtures fixtures
COPY docker docker

RUN mkdir -p backend/downloads backend/output \
    && chmod +x docker/api-entrypoint.sh docker/worker-entrypoint.sh

EXPOSE 8010

CMD ["docker/api-entrypoint.sh"]
```

- [ ] **Step 2: Create API entrypoint**

Create `docker/api-entrypoint.sh`:

```sh
#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse


def wait_for_tcp(name: str, url: str, default_port: int) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    deadline = time.monotonic() + 60
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{name} is reachable at {host}:{port}", flush=True)
                return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for {name} at {host}:{port}") from exc
            print(f"Waiting for {name} at {host}:{port}...", flush=True)
            time.sleep(2)


wait_for_tcp("postgres", os.environ.get("CLIPFORGE_DATABASE_URL") or os.environ.get("DATABASE_URL") or "postgresql://postgres:postgres@postgres:5432/postgres", 5432)
wait_for_tcp("redis", os.environ.get("CLIPFORGE_REDIS_URL") or os.environ.get("REDIS_URL") or "redis://redis:6379/0", 6379)
PY

python -m alembic -c backend/alembic.ini upgrade head
exec python -m uvicorn backend.main:app --host 0.0.0.0 --port 8010
```

- [ ] **Step 3: Create worker entrypoint**

Create `docker/worker-entrypoint.sh`:

```sh
#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import time
from urllib.parse import urlparse


def wait_for_tcp(name: str, url: str, default_port: int) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    deadline = time.monotonic() + 60
    while True:
        try:
            with socket.create_connection((host, port), timeout=2):
                print(f"{name} is reachable at {host}:{port}", flush=True)
                return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for {name} at {host}:{port}") from exc
            print(f"Waiting for {name} at {host}:{port}...", flush=True)
            time.sleep(2)


wait_for_tcp("postgres", os.environ.get("CLIPFORGE_DATABASE_URL") or os.environ.get("DATABASE_URL") or "postgresql://postgres:postgres@postgres:5432/postgres", 5432)
wait_for_tcp("redis", os.environ.get("CLIPFORGE_REDIS_URL") or os.environ.get("REDIS_URL") or "redis://redis:6379/0", 6379)
PY

exec python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q "${CLIPFORGE_CELERY_QUEUE:-clipforge-agent}"
```

- [ ] **Step 4: Run contract tests and verify backend file assertions pass**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract -v
```

Expected: still FAIL because Compose and docs are not complete. The Dockerfile and entrypoint tests should pass.

- [ ] **Step 5: Commit backend Docker image files**

Run:

```bash
git add Dockerfile.backend docker/api-entrypoint.sh docker/worker-entrypoint.sh
git commit -m "feat: add backend docker runtime"
```

---

### Task 3: Add Frontend Docker Image

**Files:**
- Create: `Dockerfile.frontend`

- [ ] **Step 1: Create frontend Dockerfile**

Create `Dockerfile.frontend`:

```dockerfile
FROM node:20-slim AS deps

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-slim AS builder

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY package.json package-lock.json next.config.js postcss.config.js tailwind.config.ts tsconfig.json ./
COPY src src
RUN npm run build

FROM node:20-slim AS runner

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    HOSTNAME=0.0.0.0 \
    PORT=3000

COPY --from=builder /app/package.json /app/package-lock.json ./
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/next.config.js ./next.config.js

EXPOSE 3000

CMD ["npm", "run", "start"]
```

The repo currently does not have a `public/` directory, so the Dockerfile intentionally does not copy it. If a future task adds `public/`, add `COPY --from=builder /app/public ./public` then.

- [ ] **Step 2: Run frontend image contract tests**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract -v
```

Expected: still FAIL because Compose and docs are not complete. Dockerfile existence assertions should pass.

- [ ] **Step 3: Commit frontend Dockerfile**

Run:

```bash
git add Dockerfile.frontend
git commit -m "feat: add frontend docker runtime"
```

---

### Task 4: Expand Docker Compose To Full Runtime

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Replace infrastructure-only Compose with full stack**

Replace `docker-compose.yml` with:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-clipforge}
      POSTGRES_USER: ${POSTGRES_USER:-clipforge}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-clipforge}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - clipforge-postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER:-clipforge} -d $${POSTGRES_DB:-clipforge}"]
      interval: 10s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "${REDIS_PORT:-6379}:6379"
    volumes:
      - clipforge-redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 10

  api:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      CLIPFORGE_DATABASE_URL: ${CLIPFORGE_DATABASE_URL:-postgresql+psycopg://clipforge:clipforge@postgres:5432/clipforge}
      CLIPFORGE_REDIS_URL: ${CLIPFORGE_REDIS_URL:-redis://redis:6379/0}
      CELERY_BROKER_URL: ${CELERY_BROKER_URL:-redis://redis:6379/0}
      CELERY_RESULT_BACKEND: ${CELERY_RESULT_BACKEND:-redis://redis:6379/0}
      CLIPFORGE_CELERY_QUEUE: ${CLIPFORGE_CELERY_QUEUE:-clipforge-agent}
      CLIPFORGE_PLANNER_MODE: ${CLIPFORGE_PLANNER_MODE:-langchain}
      CLIPFORGE_PLANNER_MODEL: ${CLIPFORGE_PLANNER_MODEL:-gpt-4o-mini}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL:-}
      FIXTURE_PROVIDER_ENABLED: ${FIXTURE_PROVIDER_ENABLED:-true}
      FIXTURE_LIBRARY_PATH: ${FIXTURE_LIBRARY_PATH:-fixtures/videos.json}
      CLIPFORGE_ASSET_PROVIDER_ORDER: ${CLIPFORGE_ASSET_PROVIDER_ORDER:-fixture,pexels,youtube}
      PEXELS_PROVIDER_ENABLED: ${PEXELS_PROVIDER_ENABLED:-true}
      PEXELS_API_KEY: ${PEXELS_API_KEY:-}
      YTDLP_PROVIDER_ENABLED: ${YTDLP_PROVIDER_ENABLED:-true}
      YTDLP_COOKIES_FILE: ${YTDLP_COOKIES_FILE:-}
      YTDLP_PLAYER_CLIENTS: ${YTDLP_PLAYER_CLIENTS:-mweb,web_safari,web}
      YTDLP_PO_TOKEN: ${YTDLP_PO_TOKEN:-}
      YTDLP_IMPERSONATE: ${YTDLP_IMPERSONATE:-}
      YTDLP_FORMAT: ${YTDLP_FORMAT:-}
    ports:
      - "${CLIPFORGE_API_PORT:-8010}:8010"
    volumes:
      - clipforge-downloads:/app/backend/downloads
      - clipforge-output:/app/backend/output
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=2)); raise SystemExit(0 if data.get('status') == 'ok' else 1)"]
      interval: 10s
      timeout: 5s
      retries: 12

  worker:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      CLIPFORGE_DATABASE_URL: ${CLIPFORGE_DATABASE_URL:-postgresql+psycopg://clipforge:clipforge@postgres:5432/clipforge}
      CLIPFORGE_REDIS_URL: ${CLIPFORGE_REDIS_URL:-redis://redis:6379/0}
      CELERY_BROKER_URL: ${CELERY_BROKER_URL:-redis://redis:6379/0}
      CELERY_RESULT_BACKEND: ${CELERY_RESULT_BACKEND:-redis://redis:6379/0}
      CLIPFORGE_CELERY_QUEUE: ${CLIPFORGE_CELERY_QUEUE:-clipforge-agent}
      CLIPFORGE_PLANNER_MODE: ${CLIPFORGE_PLANNER_MODE:-langchain}
      CLIPFORGE_PLANNER_MODEL: ${CLIPFORGE_PLANNER_MODEL:-gpt-4o-mini}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      OPENAI_BASE_URL: ${OPENAI_BASE_URL:-}
      FIXTURE_PROVIDER_ENABLED: ${FIXTURE_PROVIDER_ENABLED:-true}
      FIXTURE_LIBRARY_PATH: ${FIXTURE_LIBRARY_PATH:-fixtures/videos.json}
      CLIPFORGE_ASSET_PROVIDER_ORDER: ${CLIPFORGE_ASSET_PROVIDER_ORDER:-fixture,pexels,youtube}
      PEXELS_PROVIDER_ENABLED: ${PEXELS_PROVIDER_ENABLED:-true}
      PEXELS_API_KEY: ${PEXELS_API_KEY:-}
      YTDLP_PROVIDER_ENABLED: ${YTDLP_PROVIDER_ENABLED:-true}
      YTDLP_COOKIES_FILE: ${YTDLP_COOKIES_FILE:-}
      YTDLP_PLAYER_CLIENTS: ${YTDLP_PLAYER_CLIENTS:-mweb,web_safari,web}
      YTDLP_PO_TOKEN: ${YTDLP_PO_TOKEN:-}
      YTDLP_IMPERSONATE: ${YTDLP_IMPERSONATE:-}
      YTDLP_FORMAT: ${YTDLP_FORMAT:-}
    command: ["docker/worker-entrypoint.sh"]
    volumes:
      - clipforge-downloads:/app/backend/downloads
      - clipforge-output:/app/backend/output
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      api:
        condition: service_healthy

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    environment:
      CLIPFORGE_API_ORIGIN: ${CLIPFORGE_API_ORIGIN:-http://api:8010}
    ports:
      - "${CLIPFORGE_FRONTEND_PORT:-3000}:3000"
    depends_on:
      api:
        condition: service_healthy

volumes:
  clipforge-postgres-data:
  clipforge-redis-data:
  clipforge-downloads:
  clipforge-output:
```

This removes hard-coded `container_name` values so multiple worktrees or deployments do not collide by default.

- [ ] **Step 2: Validate Compose syntax**

Run:

```bash
docker compose config
```

Expected: command exits 0 and prints resolved services.

- [ ] **Step 3: Run contract tests**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract -v
```

Expected: README and `.env.example` assertions still fail. Compose assertions should pass.

- [ ] **Step 4: Commit Compose stack**

Run:

```bash
git add docker-compose.yml
git commit -m "feat: expand docker compose runtime"
```

---

### Task 5: Update Environment Template For Compose Deployment

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Replace `.env.example` with deployment-first defaults**

Replace `.env.example` with:

```env
# ClipForge Docker Compose deployment defaults.
# Copy this file to .env before running:
# docker compose up --build -d

# PostgreSQL container settings
POSTGRES_DB=clipforge
POSTGRES_USER=clipforge
POSTGRES_PASSWORD=clipforge
POSTGRES_PORT=5432

# Redis container settings
REDIS_PORT=6379

# ClipForge service ports
CLIPFORGE_FRONTEND_PORT=3000
CLIPFORGE_API_PORT=8010

# Compose-internal service URLs. Use service names, not localhost.
CLIPFORGE_DATABASE_URL=postgresql+psycopg://clipforge:clipforge@postgres:5432/clipforge
CLIPFORGE_REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CLIPFORGE_CELERY_QUEUE=clipforge-agent
CLIPFORGE_API_ORIGIN=http://api:8010

# Planner
# For real use, keep langchain and provide OPENAI_API_KEY.
# For deployment smoke without model calls, use deterministic.
CLIPFORGE_PLANNER_MODE=langchain
CLIPFORGE_PLANNER_MODEL=gpt-4o-mini
OPENAI_API_KEY=
OPENAI_BASE_URL=

# External asset providers
FIXTURE_PROVIDER_ENABLED=true
FIXTURE_LIBRARY_PATH=fixtures/videos.json
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
PEXELS_PROVIDER_ENABLED=true
PEXELS_API_KEY=

# YouTube / yt-dlp provider tuning
YTDLP_PROVIDER_ENABLED=true
YTDLP_COOKIES_FILE=
YTDLP_PLAYER_CLIENTS=mweb,web_safari,web
YTDLP_PO_TOKEN=
YTDLP_IMPERSONATE=
YTDLP_FORMAT=
```

- [ ] **Step 2: Run contract tests**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract -v
```

Expected: README assertions still fail. `.env.example` assertions should pass.

- [ ] **Step 3: Commit environment template**

Run:

```bash
git add .env.example
git commit -m "docs: update compose environment template"
```

---

### Task 6: Document One-Click Docker Deployment

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add Docker deployment section near the top of README**

After the 技术栈 section, add:

````markdown
## Docker 一键部署

这个方式用于单台服务器或 VPS 的小规模试用部署。它会启动完整运行栈：

- Next.js frontend
- FastAPI API
- Celery worker
- PostgreSQL
- Redis

### 1. 准备环境变量

```bash
cp .env.example .env
```

默认 `.env.example` 使用 Docker Compose 内部服务名：

- `postgres`
- `redis`
- `api`

真实使用时至少填写：

```env
OPENAI_API_KEY=<your-openai-key>
PEXELS_API_KEY=<your-pexels-key>
CLIPFORGE_PLANNER_MODE=langchain
CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube
```

如果只是验证部署和出片链路，可以先使用 fixture-first smoke 配置，避免依赖外部模型和素材源：

```env
CLIPFORGE_PLANNER_MODE=deterministic
FIXTURE_PROVIDER_ENABLED=true
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
```

### 2. 启动完整服务

```bash
docker compose up --build -d
```

### 3. 查看服务状态

```bash
docker compose ps
docker compose logs -f api worker frontend
```

### 4. 访问产品

本机访问：

```text
http://127.0.0.1:3000/workspace
```

服务器访问：

```text
http://<server-ip>:3000/workspace
```

### 5. 部署 smoke checklist

```bash
curl http://127.0.0.1:8010/health
curl -I http://127.0.0.1:3000/workspace
```

成功标准：

1. `docker compose ps` 中 `postgres`、`redis`、`api`、`worker`、`frontend` 都在运行。
2. `/health` 返回 `{"status":"ok"}`。
3. `/workspace` 可以打开。
4. 使用 fixture-first 配置创建会话并确认方案后，worker 能消费任务。
5. 如果任务成功，`/output/<file>.mp4` 能通过 frontend origin 打开。
6. 如果任务失败，`/workspace` 或 `/tasks` 显示诊断信息。

### 6. 停止服务

```bash
docker compose down
```

如需连同数据库、Redis、下载素材和渲染结果一起删除：

```bash
docker compose down -v
```
````

- [ ] **Step 2: Add a note to local development section**

In the existing `## P0 本地开发方式` section, replace the sentence:

```markdown
当前阶段只容器化 PostgreSQL 和 Redis；前端、FastAPI、Celery worker 继续在本地环境运行，不放进 Docker。
```

with:

```markdown
本地开发可以继续只启动 PostgreSQL 和 Redis，然后在宿主机运行前端、FastAPI 和 Celery worker。完整 Docker 部署方式见上方“Docker 一键部署”。
```

- [ ] **Step 3: Run contract tests**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract -v
```

Expected: all 5 tests pass.

- [ ] **Step 4: Commit README update**

Run:

```bash
git add README.md
git commit -m "docs: document docker one-click deployment"
```

---

### Task 7: Build And Smoke The Docker Stack

**Files:**
- No source changes expected unless verification reveals a concrete issue.

- [ ] **Step 1: Verify application tests outside Docker**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract tests.test_agent_backend tests.test_agent_jobs tests.test_agent_persistence -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify frontend production build outside Docker**

Run:

```bash
npm run build
```

Expected: Next.js build completes successfully.

- [ ] **Step 3: Validate Compose config**

Run:

```bash
docker compose config
```

Expected: command exits 0.

- [ ] **Step 4: Build Docker images**

Run:

```bash
docker compose build
```

Expected: backend and frontend images build successfully.

If `Dockerfile.frontend` fails because a future `public/` directory was added but not copied, add `COPY --from=builder /app/public ./public`, rebuild, and commit the fix.

- [ ] **Step 5: Start stack in fixture-first smoke mode**

For a local smoke run that does not require model or external provider keys, create a temporary `.env.docker-smoke` file:

```env
POSTGRES_DB=clipforge
POSTGRES_USER=clipforge
POSTGRES_PASSWORD=clipforge
POSTGRES_PORT=5432
REDIS_PORT=6379
CLIPFORGE_FRONTEND_PORT=3000
CLIPFORGE_API_PORT=8010
CLIPFORGE_DATABASE_URL=postgresql+psycopg://clipforge:clipforge@postgres:5432/clipforge
CLIPFORGE_REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CLIPFORGE_CELERY_QUEUE=clipforge-agent
CLIPFORGE_API_ORIGIN=http://api:8010
CLIPFORGE_PLANNER_MODE=deterministic
CLIPFORGE_PLANNER_MODEL=gpt-4o-mini
OPENAI_API_KEY=
OPENAI_BASE_URL=
FIXTURE_PROVIDER_ENABLED=true
FIXTURE_LIBRARY_PATH=fixtures/videos.json
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
PEXELS_PROVIDER_ENABLED=false
PEXELS_API_KEY=
YTDLP_PROVIDER_ENABLED=false
YTDLP_COOKIES_FILE=
YTDLP_PLAYER_CLIENTS=mweb,web_safari,web
YTDLP_PO_TOKEN=
YTDLP_IMPERSONATE=
YTDLP_FORMAT=
```

Then run:

```bash
docker compose --env-file .env.docker-smoke up --build -d
```

Expected: all services start.

- [ ] **Step 6: Verify health and frontend HTML**

Run:

```bash
docker compose --env-file .env.docker-smoke ps
curl http://127.0.0.1:8010/health
curl -I http://127.0.0.1:3000/workspace
```

Expected:

- `api`, `worker`, `frontend`, `postgres`, and `redis` are running.
- `/health` returns `{"status":"ok"}`.
- `/workspace` returns HTTP 200.

- [ ] **Step 7: Check API logs for migration success and worker readiness**

Run:

```bash
docker compose --env-file .env.docker-smoke logs --tail=120 api worker
```

Expected:

- API logs show Alembic migration reached head or no-op success.
- Worker logs show Celery ready and listening on `clipforge-agent`.

- [ ] **Step 8: Stop smoke stack without deleting volumes by default**

Run:

```bash
docker compose --env-file .env.docker-smoke down
```

If a fully clean rerun is needed, run:

```bash
docker compose --env-file .env.docker-smoke down -v
```

- [ ] **Step 9: Remove temporary smoke env file**

Run:

```bash
rm .env.docker-smoke
```

Do not commit `.env.docker-smoke`.

- [ ] **Step 10: Commit any verification-driven fixes**

If Docker verification required source fixes, stage only those files and commit with a focused message, for example:

```bash
git add Dockerfile.frontend docker-compose.yml
git commit -m "fix: harden docker smoke startup"
```

If no source fixes were needed, skip this commit.

---

### Task 8: Final Verification And Handoff

**Files:**
- No source changes expected.

- [ ] **Step 1: Run final contract and app verification**

Run:

```bash
python -m unittest tests.test_docker_deploy_contract tests.test_agent_backend tests.test_agent_jobs tests.test_agent_persistence -v
npm run build
docker compose config
```

Expected: all commands exit 0.

- [ ] **Step 2: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected:

- Branch is `codex/docker-one-click-deploy`.
- Only known pre-existing untracked `docs/superpowers/...` files may remain.
- No `.env.docker-smoke` file is present.

- [ ] **Step 3: Summarize Docker smoke outcome**

Record these in the final implementation summary:

- Whether `docker compose build` passed.
- Whether `docker compose --env-file .env.docker-smoke up --build -d` passed.
- `/health` response.
- `/workspace` HTTP status.
- Any limitations, such as skipping real external provider validation without real keys.

- [ ] **Step 4: Move to branch finishing workflow**

Use `superpowers:finishing-a-development-branch` after implementation is complete and verified. Present the standard merge/PR/keep/discard options.
