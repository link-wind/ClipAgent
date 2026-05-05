# ClipForge Agent

对话式智能剪辑 Agent。用户输入视频目标，Agent 先生成剪辑方案；用户确认后，后端搜索公开视频素材、下载素材，并用 FFmpeg 渲染为 MP4。

## 技术栈

- Next.js 14 + React 18 + TypeScript
- Zustand
- FastAPI + Pydantic
- PostgreSQL + Redis
- Celery
- yt-dlp
- FFmpeg / ffmpeg-python

## P0 本地开发方式

当前阶段只容器化 PostgreSQL 和 Redis；前端、FastAPI、Celery worker 继续在本地环境运行，不放进 Docker。

### 启动 PostgreSQL 和 Redis

```bash
docker compose up -d postgres redis
```

`docker-compose.yml` 会启动本地开发需要的 PostgreSQL 和 Redis，并分别暴露 `5432`、`6379` 端口。

### 启动 FastAPI 后端

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

如果使用项目虚拟环境：

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

### 初始化数据库

真实联调前先执行数据库迁移，避免 `agent_sessions`、`agent_jobs` 等表不存在：

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
```

### Celery 说明

`/api/agent/sessions/{id}/confirm` 现在会真实投递 Celery 任务，所以本地联调时需要单独启动 worker。

```powershell
.\.venv\Scripts\python.exe -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO
```

如果你同时开了多个 worktree，建议给当前工作区设置独立的 Redis DB 或队列名，避免不同 worker 抢同一条任务。注意这些环境变量要同时提供给后端 API 进程和 worker：

```powershell
$env:CELERY_BROKER_URL='redis://localhost:6379/1'
$env:CELERY_RESULT_BACKEND='redis://localhost:6379/1'
$env:CLIPFORGE_CELERY_QUEUE='clipforge-agent-wt1'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
.\.venv\Scripts\python.exe -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q $env:CLIPFORGE_CELERY_QUEUE
```

### 真实外部素材联调

`/workspace` 到 `/tasks` 的真实联调必须启动 PostgreSQL、Redis、FastAPI、Celery worker 和 Next.js，并使用同一个 Celery 队列名。下面示例使用独立队列，避免多个 worker 抢任务：

先准备 PostgreSQL、Redis 和数据库迁移：

```bash
docker compose up -d postgres redis
./.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

在 FastAPI 和 Celery worker 终端都设置同一组 Celery 环境变量，确保 API 发出的任务和 worker 监听的队列一致：

```bash
export CLIPFORGE_CELERY_QUEUE=clipforge-agent-ws
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

终端 A：启动 FastAPI：

```bash
./.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

终端 B：启动 Celery worker：

```bash
./.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q "$CLIPFORGE_CELERY_QUEUE"
```

终端 C：启动 Next.js：

```bash
npm run dev
```

联调验收路径：

1. 打开 `http://localhost:3000/workspace`。
2. 输入真实短视频 brief。
3. 等待 Agent 返回方案和前四个标准步骤。
4. 点击“确认方案并生成任务”。
5. 确认 `/workspace` 展示执行交接和 Job ID。
6. 打开 `/tasks`，确认同一个任务出现。
7. 等待 worker 执行真实外部素材搜索、下载和渲染。
8. 如果生成 MP4，确认 `/workspace` 或 `/tasks` 能打开结果。
9. 如果外部素材失败，记录任务详情里的失败步骤、事件日志和 worker 错误，不把该次联调记为成功。

### 启动前端

```bash
npm install
npm run dev
```

前端默认运行在 <http://localhost:3000>，并将 `/api/agent/*` 代理到后端。

## 环境变量

- `OPENAI_API_KEY`：用于生成智能剪辑方案。
- `OPENAI_BASE_URL`：可选，兼容 OpenAI API 的代理地址。
- `CLIPFORGE_API_ORIGIN`：可选，Next.js 代理目标，默认 `http://127.0.0.1:8010`。
- `CLIPFORGE_DATABASE_URL`：PostgreSQL 连接地址。
- `CLIPFORGE_REDIS_URL`：Redis 连接地址。
- `CELERY_BROKER_URL`：Celery Broker 地址。
- `CELERY_RESULT_BACKEND`：Celery 结果后端地址。
- `CLIPFORGE_CELERY_QUEUE`：Celery 默认队列名，默认 `clipforge-agent`。

本机需要可执行的 FFmpeg，后端需要能访问公开视频平台，yt-dlp 才能完成真实素材搜索和下载。

如果 YouTube 下载出现 `Precondition check failed`、`HTTP Error 400`、`nsig extraction failed`、`n challenge solving failed`，通常是本地 yt-dlp 版本太旧、JavaScript 运行时不可用，或 YouTube 播放器规则变化。先更新后端依赖：

```bash
pip install -r backend/requirements.txt --upgrade
```

项目已加入 `yt-dlp-ejs` 和 `curl-cffi`，用于提升 YouTube JS 解析和网络客户端兼容性。

本机还需要能在命令行运行 `node --version`。如果日志出现 `GVS PO Token` 或 `Only images are available for download`，说明 YouTube 对当前视频或当前网络环境要求额外 Cookie/PO Token；这种情况下 Agent 会尝试其它候选视频，但 YouTube 仍可能整体不可用。稳定生产链路建议再接入 Pexels/Pixabay/本地素材池作为备用素材源。

## 当前工作流

1. 在首页对话框输入视频目标、风格、时长和素材偏好。
2. Agent 返回结构化剪辑计划。
3. 继续对话修改计划，或点击“确认并开始”。
4. 后端搜索和下载素材，使用本地素材路径渲染成片。
5. 前端展示执行进度、结果预览和下载入口。

旧的人工时间线、素材库、检查器和浏览器端 FFmpeg 页面已经从前端移除，项目入口聚焦在智能剪辑 Agent。
