# Workspace Integration Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证并收口 `/workspace` 的 Tailwind 页面与真实后端执行链路，补齐联调证据、必要文档和收尾检查。

**Architecture:** 保持现有 `src/components/workspace/BriefWorkspacePage.tsx`、`AgentSession` 契约和 `/workspace -> /tasks` 交接结构不变，不再重复做页面迁移。重点围绕真实运行环境完成前后端联调、失败记录、验证脚本和文档更新，确保这页不仅“样式已迁移”，也能稳定驱动真实任务执行。

**Tech Stack:** Next.js 14, React 18, Tailwind CSS, FastAPI, Celery, PostgreSQL, Redis, yt-dlp, FFmpeg, Python `unittest`, Node structural checks.

---

## File Structure

- Modify `README.md`
  - 增补 `/workspace` 真实联调 runbook、环境变量说明和验收口径。
- Modify `docs/superpowers/plans/2026-05-05-workspace-tailwind-integration-implementation.md`
  - 记录当前阶段哪些项已完成，哪些改成“联调与验证”任务。
- Modify `docs/superpowers/specs/2026-05-05-workspace-tailwind-integration-design.md`
  - 只在必要时补一小段“当前状态 / 已完成 UI 迁移”说明，避免文档与代码脱节。
- Verify `src/components/workspace/BriefWorkspacePage.tsx`
  - 不预设代码修改；只在联调暴露真实缺口时再补丁。
- Verify `tests/test_agent_backend.py`
  - 使用已存在的 workspace 契约测试作为回归保护。
- Verify `scripts/check-product-pages.mjs`
  - 使用当前静态结构检查作为前端结构验收。

不扩展到 `/tasks` 新需求，不改 dashboard，不主动改后端 schema。

---

### Task 1: 基线验证当前 `/workspace` 已迁移状态

**Files:**
- Verify: `src/components/workspace/BriefWorkspacePage.tsx`
- Verify: `tests/test_agent_backend.py`
- Verify: `scripts/check-product-pages.mjs`

- [ ] **Step 1: 运行 workspace 相关前端契约测试**

Run:

```bash
./.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_is_tailwind_based \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_handoff_renders_execution_steps_and_result_states
```

Expected: PASS，说明 `/workspace` 已不再依赖 `BriefWorkspacePage.module.css`，并且保留执行交接、结果预览、失败步骤等关键入口。

- [ ] **Step 2: 运行完整后端契约测试文件**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_backend -v
```

Expected: PASS。

- [ ] **Step 3: 运行前端生产构建**

Run:

```bash
npm run build
```

Expected: build exits with code 0。

- [ ] **Step 4: 运行产品页面结构检查**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: `product page checks passed`。

- [ ] **Step 5: 记录验证结果，不改代码时也提交文档基线**

```bash
git add README.md docs/superpowers/specs/2026-05-05-workspace-tailwind-integration-design.md docs/superpowers/plans/2026-05-05-workspace-tailwind-integration-implementation.md
```

如果这一步暂时还没改文档，就先不提交，继续 Task 2。

### Task 2: 跑真实本地联调链路并收集结果

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-05-05-workspace-tailwind-integration-implementation.md`

- [ ] **Step 1: 启动依赖服务**

Run:

```bash
docker compose up -d postgres redis
```

Expected: PostgreSQL 和 Redis healthy / running。

- [ ] **Step 2: 执行数据库迁移**

Run:

```bash
./.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

Expected: migration completes without error。

- [ ] **Step 3: 启动 FastAPI**

Run:

```bash
CLIPFORGE_CELERY_QUEUE=clipforge-agent-ws \
./.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

Expected: API listens on `http://127.0.0.1:8010`。

- [ ] **Step 4: 启动 Celery worker**

Run:

```bash
CLIPFORGE_CELERY_QUEUE=clipforge-agent-ws \
./.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q clipforge-agent-ws
```

Expected: worker subscribed to `clipforge-agent-ws`。

- [ ] **Step 5: 启动前端开发服务器**

Run:

```bash
npm run dev -- --hostname 127.0.0.1 --port 3000
```

如果 3000 被占用，换到 3001 或 3002，并在文档里记下实际端口。

- [ ] **Step 6: 手动跑一次 `/workspace` 用户路径**

验证路径：
1. 打开 `/workspace`
2. 提交一个短视频 brief
3. 等待步骤 1-4 返回
4. 确认方案
5. 检查页面出现“执行交接”
6. 进入 `/tasks`，确认新 job 出现
7. 等待素材搜索、下载、渲染
8. 记录最终结果是 `videoUrl` 成功，还是明确外部素材失败

Expected: 至少拿到一条可复述的真实结果链路，而不是“理论上应该可以”。

- [ ] **Step 7: 如果失败，记录精确失败点**

记录以下之一：
- YouTube / 外部素材平台限制
- yt-dlp 反爬 / token / cookie 问题
- FFmpeg 渲染失败
- 队列、数据库、Redis 配置不一致
- 前端没有正确展示后端返回状态

不要写模糊的“联调失败”；要写带症状和命令上下文的结论。

### Task 3: 更新 runbook 与阶段文档

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-05-workspace-tailwind-integration-design.md`
- Modify: `docs/superpowers/plans/2026-05-05-workspace-tailwind-integration-implementation.md`

- [ ] **Step 1: 在 `README.md` 增补 `/workspace` 联调说明**

应覆盖：
- 依赖服务启动顺序
- 关键环境变量来源
- FastAPI / Celery / Next.js 启动命令
- `/workspace` 到 `/tasks` 的验证路径
- 成功与失败两类验收口径

- [ ] **Step 2: 在 design 文档补当前状态说明**

补一小节说明：
- `/workspace` 的 Tailwind 迁移已在代码中完成
- 当前阶段重点已转为真实联调和验证证据
- `/tasks` 已是后续独立页面，不再属于这个 design 的实现范围

- [ ] **Step 3: 在 implementation plan 文档标记已完成项与剩余项**

把旧 plan 中已完成的 Tailwind 迁移任务标记为“已完成/已落地”，并补一段当前执行建议：
- 当前下一步不是重做页面迁移
- 而是完成真实联调、记录外部素材行为、更新 runbook、准备收尾

- [ ] **Step 4: 提交文档收尾**

```bash
git add README.md docs/superpowers/specs/2026-05-05-workspace-tailwind-integration-design.md docs/superpowers/plans/2026-05-05-workspace-tailwind-integration-implementation.md
git commit -m "docs: update workspace integration runbook"
```

Expected: commit contains only docs/runbook updates.

### Task 4: 最终验收与分支建议

**Files:**
- Verify only: workspace docs + current app files

- [ ] **Step 1: 重新跑最终验收顺序**

Run:

```bash
./.venv/bin/python -m unittest tests.test_agent_backend -v
npm run build
node scripts/check-product-pages.mjs
```

Expected: all pass。

- [ ] **Step 2: 汇总这轮 `/workspace` 的真实结论**

最终总结必须明确回答：
- `/workspace` 页面迁移是否已完成
- 前后端联调是否成功
- 如果失败，失败在什么外部链路
- 下一步应该优先修哪里

- [ ] **Step 3: 给出收尾选择**

收尾时只给两个选项：
1. 继续修真实联调暴露的问题
2. 合并当前阶段成果并删除分支

---

## Self-Review

- 这个 plan 不再重复已落地的 `/workspace` Tailwind 迁移实现，而是基于当前代码状态切到联调与文档收尾。
- 范围保持在 `/workspace`，没有重新把 `/tasks` 或 dashboard 拉回来。
- 验证顺序保持为先 unittest，再 build，再 product page checks，符合仓库里已经验证过的节奏。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-workspace-integration-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
