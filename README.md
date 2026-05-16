# ClipForge Agent

ClipForge 是一个对话式短视频剪辑 Agent。用户输入视频 brief 后，系统先生成剪辑方案；用户确认后，后端执行素材搜索、准备与渲染，最终输出 MP4。

## v0.1 状态

`v0.1` 已经完成首版可运行产品形态，当前可以用于演示、本地联调和小规模试用。

- 已完成首页、`/workspace`、`/tasks`、`/settings` 四个核心页面
- 已打通从 brief、方案、任务创建到素材搜索、渲染输出的主流程
- 已具备 FastAPI + PostgreSQL + Redis + Celery 的基础工作流
- 已接入 `fixture`、`Pexels`、`YouTube/yt-dlp` 三类素材源
- 已支持 LangChain planner 与失败降级策略
- 已支持 Docker Compose 一键部署

## 技术栈

- Next.js 14 + React 18 + TypeScript
- Tailwind CSS
- FastAPI + Pydantic
- PostgreSQL + Redis
- Celery
- FFmpeg
- yt-dlp

## Agent Runtime 架构

目标架构按清晰边界分层：API route 只负责 HTTP request/response translation，不承载业务编排；`backend/app` 是 session、planning、execution 等应用用例边界；`backend/runtime` 是 Agent orchestration layer，包含 `Context Engine`、`Skill Engine`、`Tool Gateway` 和 Trace Recorder；`backend/domain` 放稳定业务契约；`backend/infrastructure` 放数据库、LLM、media、后续 vector store 和 MCP client 等适配器；`backend/workers` 放 Celery app 和 task entrypoints。

本阶段只锁定兼容模块和边界，确保现有功能可以逐步迁入目标结构。RAG、Skill registry、MCP server/client 是下一阶段接入点，不在本阶段实现。

## 页面结构

- `/`：首页
- `/workspace`：方案沟通与执行入口
- `/tasks`：任务列表与任务详情
- `/settings`：运行配置

## Docker 快速启动

复制环境变量模板：

```bash
cp .env.example .env
```

启动完整服务：

```bash
docker compose up --build -d
```

访问地址：

- 前端：<http://127.0.0.1:3000>
- Workspace：<http://127.0.0.1:3000/workspace>
- 后端健康检查：<http://127.0.0.1:8010/health>

停止服务：

```bash
docker compose down
```

## 本地开发

先启动基础依赖：

```bash
docker compose up -d postgres redis
```

执行数据库迁移：

```bash
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

启动后端：

```bash
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

启动 worker：

```bash
.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO
```

启动前端：

```bash
npm install
npm run dev -- --hostname 127.0.0.1 --port 3000
```

## 核心环境变量

- `OPENAI_API_KEY`：OpenAI 兼容服务 key
- `OPENAI_BASE_URL`：OpenAI 兼容服务地址
- `CLIPFORGE_PLANNER_MODE`：planner 运行模式，默认 `langchain`；设为 `deterministic` 可回退到规则版 planner。
- `CLIPFORGE_PLANNER_MODEL`：planner 使用的模型名
- `CLIPFORGE_API_ORIGIN`：前端代理的后端地址，默认 `http://127.0.0.1:8010`
- `CLIPFORGE_DATABASE_URL`：PostgreSQL 连接地址
- `CLIPFORGE_REDIS_URL`：Redis 连接地址
- `CELERY_BROKER_URL`：Celery broker
- `CELERY_RESULT_BACKEND`：Celery result backend
- `CLIPFORGE_CELERY_QUEUE`：Celery 队列名
- `CLIPFORGE_ASSET_PROVIDER_ORDER`：素材源顺序，例如 `fixture,pexels,youtube`
- `PEXELS_API_KEY`：Pexels API key
- `YTDLP_COOKIES_FILE`：可选，YouTube cookies 文件
- `YTDLP_PO_TOKEN`：可选，YouTube PO Token

## 素材源说明

仓库内置 deterministic fixture provider，用于 smoke / demo / 本地演示时稳定验证产品链路；真实外部 provider 验证则用于确认 Pexels、YouTube 等外部素材源是否能完成搜索、下载和渲染。

- `fixture`：本地稳定 smoke/demo
- `pexels`：更稳定的公开视频搜索源
- `youtube`：补充素材源，但更受网络和平台限制影响

推荐：

- 演示 / 冒烟：`fixture,pexels,youtube`
- 真实外部素材联调：`pexels,youtube`
