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

`/workspace` 到 `/tasks` 的真实联调必须启动 PostgreSQL、Redis、FastAPI、Celery worker 和 Next.js，并使用同一个 Celery 队列名。下面示例使用独立队列，避免多个 worker 抢任务。

如果你在 `.worktrees/` 下运行联调，通常会直接复用仓库根目录的虚拟环境 `/Users/linkwind/Code/ClipForge_v2/.venv`。新的 worktree 默认不会自带 `./.venv`，因此命令里的 Python 路径要么写成仓库根的绝对路径，要么先自行建立共享虚拟环境策略。

另外，当前 `docker-compose.yml` 为 PostgreSQL 和 Redis 写死了 `container_name`。如果本机已经有 `clipforge-postgres` / `clipforge-redis` 在跑，新的 worktree 不必再强行起第二套容器，直接复用现有依赖即可；否则会遇到容器名冲突。2026-05-06 的 P0 hardening 真实联调就是复用本机已运行的这两个容器。

先准备 PostgreSQL、Redis 和数据库迁移。如果容器已经在运行，可以跳过 `docker compose up`，但仍要确认数据库迁移已执行：

```bash
docker compose up -d postgres redis
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

在 FastAPI 和 Celery worker 终端都设置同一组 Celery 环境变量，确保 API 发出的任务和 worker 监听的队列一致。P0 hardening 真实联调用到的队列和 provider 顺序如下：

```bash
export CLIPFORGE_CELERY_QUEUE=clipforge-agent-p0
export CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube
export CELERY_BROKER_URL=redis://localhost:6379/1
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

终端 A：启动 FastAPI。P0 hardening 真实联调使用 `127.0.0.1:8011`，如果该端口被占用，可以换空闲端口，但要同步设置前端代理目标：

```bash
CLIPFORGE_CELERY_QUEUE="$CLIPFORGE_CELERY_QUEUE" \
CLIPFORGE_ASSET_PROVIDER_ORDER="$CLIPFORGE_ASSET_PROVIDER_ORDER" \
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8011
```

终端 B：启动 Celery worker：

```bash
CLIPFORGE_CELERY_QUEUE="$CLIPFORGE_CELERY_QUEUE" \
CLIPFORGE_ASSET_PROVIDER_ORDER="$CLIPFORGE_ASSET_PROVIDER_ORDER" \
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q "$CLIPFORGE_CELERY_QUEUE"
```

终端 C：启动 Next.js。P0 hardening 真实联调使用 `127.0.0.1:3002`，并把前端代理指向 `127.0.0.1:8011`：

```bash
CLIPFORGE_API_ORIGIN=http://127.0.0.1:8011 npm run dev -- --hostname 127.0.0.1 --port 3002
```

联调验收路径：

1. 打开 `http://127.0.0.1:3002/workspace`，或使用本次实际前端端口。
2. 输入真实短视频 brief。
3. 等待 Agent 返回方案和前四个标准步骤。
4. 点击“确认方案并生成任务”。
5. 确认 `/workspace` 展示执行交接和 Job ID。
6. 打开 `/tasks`，确认同一个任务出现。
7. 等待 worker 执行真实外部素材搜索、下载和渲染。
8. 如果生成 MP4，确认 `/workspace` 或 `/tasks` 能打开结果。
9. 如果外部素材失败，记录任务详情里的失败步骤、事件日志和 worker 错误，不把该次联调记为成功。

2026-05-06 的 P0 hardening 真实联调记录：

- 运行环境复用本机已运行的 `clipforge-postgres` / `clipforge-redis`，backend 为 `127.0.0.1:8011`，frontend 为 `127.0.0.1:3002`，queue 为 `clipforge-agent-p0`，provider order 为 `pexels,youtube`。
- 本机未配置 `PEXELS_API_KEY`，因此 Pexels provider 不能完成真实素材搜索；这类 run 不能记为“稳定出片”成功。
- 第一条真实联调 session 为 `34ad731d-b7d3-4095-96fa-1ae899481fd1`，job 为 `e27a7261-599d-4062-a6ef-2e1436474b76`。`/workspace -> confirm -> /tasks -> worker` 链路成功，最终失败在 `search_assets`。
- 第一条失败原因是 Pexels 没有 API key，YouTube 搜索出现 connection reset / timeout。结论是产品交接链路已验证，但外部素材源不可用。
- Task 3 后做过两次最小修补：`8e9ded4 fix: dedupe provider failure diagnostics` 去重 provider 失败诊断，`79e41f1 fix: collapse repeated scene provider failures` 折叠重复 scene provider 失败。
- 第二条真实联调仍失败在 `search_assets`，但 provider failure 聚合已更清晰，不再无限累加同类 scene 错误。
- 当前阶段尚未达到“稳定出片”标准。没有 `PEXELS_API_KEY` 时，`pexels,youtube` 会退到受外部网络和平台限制影响较大的 YouTube 路径；如果 YouTube connection reset 或 timeout，本次失败应归类为 asset search / provider availability failure，而不是 worker、任务交接或渲染失败。

### Deterministic fixture mode

仓库现在内置了一个 deterministic 本地素材源 `fixture`，用于本地 P0 验证、演示和前后端联调。它会读取 `fixtures/videos.json`，按简单关键词重叠匹配本地样例素材，再把命中的 `.mp4` 复制到 `backend/downloads/`，继续复用现有渲染链路。

这条链路的目标不是替代真实外部素材，而是在外部 provider 不稳定、没有 API key、或者只是想验证产品流程时，提供一条稳定出片路径。当前仓库已经附带 5 个极小的本地 fixture mp4，用来保证 demo 和自动化测试都能真正走到 MP4 输出。

推荐用法：

- demo / 本地演示：`CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube`
- 真实外部素材联调：`CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube`

fixture mode 的成功口径是：从 `/workspace` 或 `/tasks` 发起任务后，worker 能稳定完成素材命中、复制和渲染，最终产出可访问的 MP4。它验证的是产品工作流和渲染链路，不代表真实外部 provider 也已经稳定。

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
- `YTDLP_PROVIDER_ENABLED`：可选，是否启用 YouTube/yt-dlp 素材源，默认启用。
- `YTDLP_COOKIES_FILE`：可选，Netscape cookies 文件路径，用于 YouTube 要求登录或验证时的本地联调。只配置路径，不提交 cookie 文件。
- `YTDLP_PLAYER_CLIENTS`：可选，yt-dlp YouTube client 顺序，默认 `mweb,web_safari,web`。
- `YTDLP_PO_TOKEN`：可选，yt-dlp YouTube PO Token 配置字符串。只有在本机已经按 yt-dlp 文档配置好 token 流程时再使用。
- `YTDLP_IMPERSONATE`：可选，浏览器 TLS 指纹模拟值，例如 `chrome`。
- `YTDLP_FORMAT`：可选，覆盖 yt-dlp 下载格式选择；默认优先 720p 左右的 MP4。
- `FIXTURE_PROVIDER_ENABLED`：可选，是否启用本地 deterministic fixture provider，默认启用。
- `FIXTURE_LIBRARY_PATH`：可选，本地 fixture metadata 路径，默认 `fixtures/videos.json`。
- `CLIPFORGE_ASSET_PROVIDER_ORDER`：可选，素材源搜索顺序，默认 `youtube,pexels`。demo / 稳定演示建议使用 `fixture,pexels,youtube`；真实外部素材联调如果 YouTube 经常超时或反爬，可改成 `pexels,youtube`。
- `PEXELS_PROVIDER_ENABLED`：可选，是否启用 Pexels 素材源；当 `PEXELS_API_KEY` 存在时默认启用。
- `PEXELS_API_KEY`：Pexels API key，用于稳定搜索和下载公开视频素材。

本机需要可执行的 FFmpeg，后端需要能访问公开视频平台，yt-dlp 才能完成真实素材搜索和下载。

如果 YouTube 下载出现 `Precondition check failed`、`HTTP Error 400`、`nsig extraction failed`、`n challenge solving failed`，通常是本地 yt-dlp 版本太旧、JavaScript 运行时不可用，或 YouTube 播放器规则变化。先更新后端依赖：

```bash
pip install -r backend/requirements.txt --upgrade
```

项目已加入 `yt-dlp-ejs` 和 `curl-cffi`，用于提升 YouTube JS 解析和网络客户端兼容性。

本机还需要能在命令行运行 `node --version`。如果日志出现 `GVS PO Token`、`Only images are available for download` 或 `Sign in to confirm you’re not a bot`，说明 YouTube 对当前视频、账号、客户端或网络环境要求额外 Cookie/PO Token。可以先尝试：

1. 升级后端依赖：`pip install -r backend/requirements.txt --upgrade`。
2. 配置 `YTDLP_COOKIES_FILE` 指向本机导出的 Netscape cookies 文件。
3. 按 yt-dlp 官方文档配置 PO Token 后填写 `YTDLP_PO_TOKEN`。
4. 用 `YTDLP_PLAYER_CLIENTS` 或 `YTDLP_IMPERSONATE` 调整本地联调环境。

这些配置只能降低 YouTube 失败概率，不能保证 YouTube 永久稳定。生产和稳定联调建议配置 `PEXELS_API_KEY`，并把 `CLIPFORGE_ASSET_PROVIDER_ORDER` 调整为 `pexels,youtube`，让 worker 先走更稳定的 Pexels 搜索链路。Pexels 视频搜索使用官方 `https://api.pexels.com/v1/videos/search` endpoint，并通过 `Authorization` header 传入 API key。

失败任务会保留素材源诊断信息。看到 `youtube: ...`、`pexels: ...` 这类错误时，先确认对应 provider 的环境变量和外部网络，再决定是否禁用某个 provider 做单独排查。

排查 provider 顺序或单独验证时，可以临时设置：

```bash
CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube
YTDLP_PROVIDER_ENABLED=false
PEXELS_PROVIDER_ENABLED=true
```

这会优先走 Pexels，并且在上面示例里直接跳过 YouTube，只验证 Pexels 搜索、下载和渲染链路。反过来设置 `PEXELS_PROVIDER_ENABLED=false` 可以只验证 YouTube/yt-dlp 链路。

如果只是验证产品链路是否能稳定出片，推荐直接使用：

```bash
FIXTURE_PROVIDER_ENABLED=true
FIXTURE_LIBRARY_PATH=fixtures/videos.json
CLIPFORGE_ASSET_PROVIDER_ORDER=fixture,pexels,youtube
```

这会优先命中仓库内的本地 fixture 素材，不依赖外部网络，也不要求 `PEXELS_API_KEY`。一旦 fixture 没命中，worker 仍会继续尝试后面的真实 provider。

## 当前工作流

1. 在首页对话框输入视频目标、风格、时长和素材偏好。
2. Agent 返回结构化剪辑计划。
3. 继续对话修改计划，或点击“确认并开始”。
4. 后端搜索和下载素材，使用本地素材路径渲染成片。
5. 前端展示执行进度、结果预览和下载入口。

旧的人工时间线、素材库、检查器和浏览器端 FFmpeg 页面已经从前端移除，项目入口聚焦在智能剪辑 Agent。
