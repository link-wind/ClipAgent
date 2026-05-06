# P0 Workflow Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 验证并加固 ClipForge 从 `/workspace` 到 `/tasks` 再到 MP4 成片的真实工作流，补齐失败恢复、联调证据与发布前 runbook。

**Architecture:** 保持现有三页产品流、现有后端 schema、现有任务与步骤契约不变。先用真实本地环境跑通并记录工作流，再只对真实暴露的缺口做最小修补，最后把启动顺序、环境变量、失败口径和验证命令写回文档。

**Tech Stack:** Next.js 14, React 18, Tailwind CSS, FastAPI, Celery, PostgreSQL, Redis, Python `unittest`, Alembic, FFmpeg, yt-dlp, Pexels API, Node structural page checks.

---

## File Structure

- Modify: `README.md`
  - 对齐真实启动顺序、环境变量、成功/失败验收口径、provider 配置说明。
- Modify: `docs/superpowers/specs/2026-05-06-p0-workflow-hardening-design.md`
  - 只在需要时补“已验证 / 已决议”小节，保持 spec 与执行结果一致。
- Modify: `docs/superpowers/plans/2026-05-06-p0-workflow-hardening.md`
  - 记录任务完成状态与执行建议。
- Modify if needed: `backend/services/agent_step_snapshot_service.py`
  - 只在真实联调证明 failed step 映射不准确时修补。
- Modify if needed: `backend/services/agent_progress_service.py`
  - 只在真实联调证明错误分类或 retryable step 落点错误时修补。
- Modify if needed: `src/components/workspace/BriefWorkspacePage.tsx`
  - 只在真实联调暴露恢复/失败指引不清时补最小 UI 文案或映射。
- Modify if needed: `src/components/tasks/TaskManagerPage.tsx`
  - 只在真实联调暴露任务详情失败文案、结果入口或恢复动作不清时补最小 UI 文案。
- Modify if needed: `tests/test_agent_backend.py`
  - 先写失败测试锁定真实暴露的问题，再做最小实现。
- Verify: `scripts/check-product-pages.mjs`
  - 保持 build 后结构检查有效。

不做 dashboard 方向重开，不做全站 Tailwind 迁移，不主动扩展 API 契约，不做大规模 worker / orchestration 重构。

---

### Task 1: 锁定当前基线并验证现有工作流契约

**Files:**
- Verify: `tests/test_agent_backend.py`
- Verify: `src/components/workspace/BriefWorkspacePage.tsx`
- Verify: `src/components/tasks/TaskManagerPage.tsx`
- Verify: `backend/services/agent_step_snapshot_service.py`
- Verify: `scripts/check-product-pages.mjs`

- [x] **Step 1: 运行 workspace 与 tasks 关键前端契约测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_renders_resume_actions \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_restore_experience_can_jump_to_result_failure_or_execution \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_workspace_jump_clears_session_before_setting_active_session \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_list_rows_do_not_render_active_retry_action
```

Expected: PASS。

- [x] **Step 2: 运行后端 provider 与失败映射相关测试**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_stops_searching_after_first_provider_returns_candidates \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_download_failure_surfaces_last_external_error \
  tests.test_agent_backend.AgentExecutionContractTests.test_agent_search_failure_surfaces_external_error
```

Expected: PASS。

- [x] **Step 3: 运行完整测试、生产构建与结构检查**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
npm run build
node scripts/check-product-pages.mjs
```

Expected:

- unittest: `OK`
- build: exit code 0
- structural check: `product page checks passed`

- [x] **Step 4: 记录当前基线结论**

在执行笔记中明确记录：

- `/workspace` 恢复链路当前已具备
- `/tasks` B1 列表 + 弹窗详情当前已具备
- provider order 当前支持 `pexels,youtube`
- 当前仍待验证的是“真实本地环境下是否稳定跑通”

执行结果（2026-05-06）：
- workspace/tasks 前端契约测试 6 项通过；provider/失败映射相关测试 3 项通过；完整 `tests.test_agent_backend` 66 项通过。
- `npm run build` 退出码 0；`node scripts/check-product-pages.mjs` 输出 `product page checks passed`。
- 记录到的 warning/诊断：SQLAlchemy `datetime.utcnow()` DeprecationWarning；测试路径中出现 YouTube PO Token 下载跳过诊断。

- [x] **Step 5: 提交基线验证结论（仅当本任务实际修改了文档或测试时）**

执行结果：已提交 commit `6033a9c test: lock p0 workflow hardening baseline`。

```bash
git add tests/test_agent_backend.py README.md docs/superpowers/specs/2026-05-06-p0-workflow-hardening-design.md docs/superpowers/plans/2026-05-06-p0-workflow-hardening.md
git commit -m "test: lock p0 workflow hardening baseline"
```

如果 Task 1 只做验证、不改文件，则跳过提交，继续 Task 2。

### Task 2: 跑一条真实端到端本地链路并收集证据

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-05-06-p0-workflow-hardening.md`

- [ ] **Step 1: 启动基础依赖**

Run:

```bash
docker compose up -d postgres redis
```

Expected: PostgreSQL 与 Redis running。

- [ ] **Step 2: 执行数据库迁移**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
```

Expected: migration completes without error。

- [ ] **Step 3: 设定本次联调环境变量**

在当前 shell 中设定：

```bash
export CLIPFORGE_CELERY_QUEUE=clipforge-agent-p0
export CLIPFORGE_ASSET_PROVIDER_ORDER=pexels,youtube
```

如果本机已经配置 `PEXELS_API_KEY`，保留它；如果没有，就明确记录“当前 run 将受外部素材源能力限制”。

- [ ] **Step 4: 启动 FastAPI**

Run:

```bash
CLIPFORGE_CELERY_QUEUE="$CLIPFORGE_CELERY_QUEUE" \
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8010
```

Expected: API listens on `127.0.0.1:8010`。

- [ ] **Step 5: 启动 Celery worker**

Run:

```bash
CLIPFORGE_CELERY_QUEUE="$CLIPFORGE_CELERY_QUEUE" \
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m celery -A backend.tasks.celery_app:celery_app worker --pool solo --loglevel INFO -Q "$CLIPFORGE_CELERY_QUEUE"
```

Expected: worker subscribed to `clipforge-agent-p0`。

- [ ] **Step 6: 启动 Next.js**

Run:

```bash
npm run dev -- --hostname 127.0.0.1 --port 3000
```

如果 3000 被占用，改到空闲端口，并把实际端口写入文档。

- [ ] **Step 7: 手动跑一次真实用户路径**

执行顺序：

1. 打开 `http://127.0.0.1:3000/workspace`（或实际端口）
2. 输入一个真实短视频 brief
3. 等待步骤 1-4 返回
4. 确认方案并创建任务
5. 确认页面出现执行交接
6. 打开 `/tasks`
7. 找到新任务并打开详情
8. 观察 `search_assets -> prepare_assets -> render_video` 的实际流转
9. 记录最终是成功产出 MP4，还是停在某个失败步骤

Expected: 产出一条可复述的真实执行记录，包含 session id、job id、最终状态、失败或成功证据。

- [ ] **Step 8: 把本次联调结果写入执行文档**

必须记录：

- session id
- job id
- provider order
- 是否存在 `PEXELS_API_KEY`
- 成功时的输出路径或结果 URL
- 失败时的 failed step、错误文案、对应事件与推测分类

### Task 3: 用 TDD 修真实联调暴露的最小缺口

**Files:**
- Modify as needed: `tests/test_agent_backend.py`
- Modify as needed: `backend/services/agent_step_snapshot_service.py`
- Modify as needed: `backend/services/agent_progress_service.py`
- Modify as needed: `src/components/workspace/BriefWorkspacePage.tsx`
- Modify as needed: `src/components/tasks/TaskManagerPage.tsx`
- Modify as needed: `README.md`

- [ ] **Step 1: 只为真实暴露的问题写一个失败测试**

示例方向，按真实症状二选一或其一：

- failed step 被错误标成 `render_video`，但真实失败发生在 `search_assets`
- `/workspace` 未给出明确恢复建议
- `/tasks` 详情缺少能帮助判断 provider/config 问题的关键信息

测试必须直接落在 `tests/test_agent_backend.py`，并优先使用下面这三个明确测试名之一：

```python
    def test_failed_asset_search_maps_to_search_assets_step(self):
        ...

    def test_workspace_failed_run_shows_recovery_guidance(self):
        ...

    def test_tasks_failure_detail_surfaces_provider_guidance(self):
        ...
```

- [ ] **Step 2: 运行该测试，确认先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_failed_asset_search_maps_to_search_assets_step \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_failed_run_shows_recovery_guidance \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_failure_detail_surfaces_provider_guidance
```

Expected: 只会有一个新测试存在并失败，失败原因就是刚暴露的真实缺口；其余两个路径如果尚未创建，会在这一步前从命令里删掉未使用的测试名。

- [ ] **Step 3: 写最小实现修根因**

实现原则：

- 如果是步骤映射问题，优先修 `backend/services/agent_step_snapshot_service.py`
- 如果是错误状态记录问题，优先修 `backend/services/agent_progress_service.py`
- 如果是用户恢复指引问题，优先在 `BriefWorkspacePage.tsx` 或 `TaskManagerPage.tsx` 补最小文案
- 不新增大范围 retry 机制
- 不顺手改 unrelated UI

- [ ] **Step 4: 重跑刚才的失败测试，确认转绿**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentExecutionContractTests.test_failed_asset_search_maps_to_search_assets_step \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_failed_run_shows_recovery_guidance \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_failure_detail_surfaces_provider_guidance
```

Expected: 刚新增的那个测试 PASS；命令里未使用的测试名同样应在执行前删掉。

- [ ] **Step 5: 重跑相关回归测试**

至少重跑：

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
npm run build
node scripts/check-product-pages.mjs
```

Expected: 全部通过。

- [ ] **Step 6: 提交最小修补**

```bash
git add tests/test_agent_backend.py backend/services/agent_step_snapshot_service.py backend/services/agent_progress_service.py src/components/workspace/BriefWorkspacePage.tsx src/components/tasks/TaskManagerPage.tsx README.md
git commit -m "fix: harden p0 workflow failure recovery"
```

只提交真实改过的文件，不把未跟踪规划草稿一起带上。

### Task 4: 更新 runbook、spec 状态与阶段结论

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-06-p0-workflow-hardening-design.md`
- Modify: `docs/superpowers/plans/2026-05-06-p0-workflow-hardening.md`

- [ ] **Step 1: 在 `README.md` 固化真实启动顺序**

至少覆盖：

- `docker compose up -d postgres redis`
- Alembic migration
- FastAPI 启动命令
- Celery queue 约束
- Next.js 启动命令
- `/workspace -> /tasks -> 成片/失败` 验证顺序

- [ ] **Step 2: 在 `README.md` 明确环境变量与素材源策略**

至少覆盖：

- `CLIPFORGE_CELERY_QUEUE`
- `CLIPFORGE_ASSET_PROVIDER_ORDER`
- `PEXELS_API_KEY`
- `YTDLP_COOKIES_FILE`
- `YTDLP_PO_TOKEN`
- 什么时候推荐 `pexels,youtube`
- 什么时候应该改用本地 fixture 或 deterministic mode

- [ ] **Step 3: 在 spec 文件补已验证结论**

新增一个简短小节，说明：

- 本阶段真实跑了哪条链路
- 成功或失败证据是什么
- 已确认哪些决议
- 哪些仍留到下一小阶段

- [ ] **Step 4: 在当前 plan 中勾掉已完成项并补阶段总结**

总结至少回答：

- 本地真实工作流是否已跑通
- 失败时最常见的卡点是什么
- 当前是否已经达到“可发布演示”标准
- 下一小步是继续修失败恢复，还是转去 deterministic asset support

- [ ] **Step 5: 提交文档结论**

```bash
git add README.md docs/superpowers/specs/2026-05-06-p0-workflow-hardening-design.md docs/superpowers/plans/2026-05-06-p0-workflow-hardening.md
git commit -m "docs: update p0 workflow hardening runbook"
```

### Task 5: 最终验收与执行出口

**Files:**
- Verify only: current repo state

- [ ] **Step 1: 重新跑最终验收顺序**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
npm run build
node scripts/check-product-pages.mjs
```

Expected:

- unittest: `OK`
- build: exit code 0
- structural checks: `product page checks passed`

- [ ] **Step 2: 产出最终阶段结论**

结论必须明确回答：

- 真实工作流是否已经跑通
- 如果没完全跑通，断在哪一层
- 当前失败是环境问题、provider 问题、worker 问题，还是渲染问题
- 下一步最值得做的是继续修恢复闭环，还是补 deterministic asset support

- [ ] **Step 3: 给出执行出口**

只给两个选项：

1. **继续执行**：立刻进入 deterministic asset support / fixture fallback 的下一小阶段
2. **阶段收尾**：合并当前 P0 hardening 成果并删除分支

---

## Self-Review

- 这个 plan 覆盖了 spec 的四条主线：真实验证、失败恢复、素材可复现、release hygiene。
- 它没有重新打开 dashboard，也没有把 Tailwind 迁移外扩到无关页面。
- 每个需要改代码的阶段都要求先写失败测试、再验证失败、再做最小实现，保持 TDD。
- 验证顺序明确写成 `unittest -> build -> check-product-pages`，避免先读旧 `.next` 产物造成误报。

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-06-p0-workflow-hardening.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
