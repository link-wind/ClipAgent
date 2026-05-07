# Tasks Operations Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/tasks` 做成更易扫读、结果可直达、动作更诚实的 B1 任务控制台，同时保持现有后端契约和 `/workspace -> /tasks` 产品链路不变。

**Architecture:** 继续以 `src/components/tasks/TaskManagerPage.tsx` 为唯一页面实现面，保留 “列表 + 弹窗详情” 结构，不拆路由、不改 modal 机制。列表层通过新增本地结果缓存和更明确的行级动作，在不扩展 `AgentTaskSummary` API 的前提下，用现有 `getAgentTask()` detail 接口为已完成任务补全 `videoUrl` 可见性；同时把 `批量操作` 收敛为诚实的不可用状态，把失败提示和结果入口往主列表前移。

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand store, existing `taskApi` client, Python `unittest`, Node build-time structural checks.

---

## File Structure

- Modify: `src/components/tasks/TaskManagerPage.tsx`
  - 增加结果 URL 缓存、列表行结果入口、诚实的批量操作提示、失败强调样式与更清晰的主列表文案。
- Modify: `tests/test_agent_backend.py`
  - 为新的运营可用性 contract 增加源码级断言：列表行动作、结果缓存 wiring、批量操作诚实文案、结果入口文案。
- Modify: `scripts/check-product-pages.mjs`
  - 更新静态 `/tasks` 页面断言，使其校验新的运营控制台文案与操作入口。

Do not modify:

- `backend/models/agent.py`
- `backend/services/agent_task_read_service.py`
- `/workspace` 页面结构
- `/tasks` B2/B3 concept 页面

---

### Task 1: 锁定 `/tasks` 运营可用性 contract

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_operations_console_copy`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_row_actions_include_workspace_and_result_paths`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_batch_action_is_honest_placeholder`

- [ ] **Step 1: 在 `FrontendClientContractTests` 里加入 3 个失败测试**

在 `tests/test_agent_backend.py` 里、紧接着现有 `/tasks` 相关测试后面，加入：

```python
    def test_tasks_operations_console_copy(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("任务控制台", tasks_source)
        self.assertIn("统一扫读任务状态、最近活动和结果入口", tasks_source)
        self.assertIn("失败优先关注", tasks_source)
        self.assertIn("结果直达", tasks_source)

    def test_tasks_row_actions_include_workspace_and_result_paths(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("const [taskVideoUrls, setTaskVideoUrls] = useState<Record<string, string>>({});", tasks_source)
        self.assertIn("function openTaskResult(taskId: string)", tasks_source)
        self.assertIn("taskVideoUrls[task.id]", tasks_source)
        self.assertIn("打开结果", tasks_source)
        self.assertIn("查看方案", tasks_source)

    def test_tasks_batch_action_is_honest_placeholder(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("批量操作将在后续阶段开放", tasks_source)
        self.assertIn("本阶段先支持单任务查看、回到方案和结果直达。", tasks_source)
        self.assertIn("disabled", tasks_source)
```

- [ ] **Step 2: 运行 3 个新测试，确认它们先失败**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_operations_console_copy \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_row_actions_include_workspace_and_result_paths \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_batch_action_is_honest_placeholder
```

Expected: FAIL，因为 `TaskManagerPage.tsx` 里还没有新的“任务控制台”文案、`taskVideoUrls` 结果缓存状态，也没有诚实的批量操作提示文案。

- [ ] **Step 3: 提交测试红灯基线**

Run:

```bash
git add tests/test_agent_backend.py
git commit -m "test: lock tasks operations usability contract"
```

---

### Task 2: 在前端增加结果缓存与行级动作 helper

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_row_actions_include_workspace_and_result_paths`
- Test: `npm run build`

- [ ] **Step 1: 增加结果缓存与详情缓存状态**

在 `TaskManagerPage.tsx` 的 state 区域、`activeTask` 之后加入：

```tsx
  const [taskVideoUrls, setTaskVideoUrls] = useState<Record<string, string>>({});
  const [taskResultLoadingIds, setTaskResultLoadingIds] = useState<Record<string, boolean>>({});
```

这两个 state 的职责：

- `taskVideoUrls`: 保存已确认存在结果 URL 的任务 `id -> videoUrl`
- `taskResultLoadingIds`: 防止同一任务重复请求 detail

- [ ] **Step 2: 增加行级结果判定 helper**

在 `getEventTimestamp()` 后面加入这些 helper：

```tsx
function isCompletedTask(status: string) {
  return status === 'completed' || status === 'done' || status === 'succeeded';
}

function isFailedTask(status: string) {
  return status === 'failed' || status === 'error';
}

function getTaskRowAccentClasses(task: AgentTaskSummary, hasResult: boolean) {
  if (isFailedTask(task.status)) {
    return 'border-rose-200 bg-rose-50/60';
  }
  if (hasResult) {
    return 'border-emerald-200 bg-emerald-50/50';
  }
  return 'border-border bg-white';
}
```

- [ ] **Step 3: 增加 detail 预取函数，只为可能已有结果的任务拉取 URL**

在 `refreshActiveTaskDetail()` 后面加入：

```tsx
  async function primeTaskResult(taskId: string) {
    if (taskVideoUrls[taskId] || taskResultLoadingIds[taskId]) {
      return;
    }

    setTaskResultLoadingIds((prev) => ({ ...prev, [taskId]: true }));

    try {
      const detail = await getAgentTask(taskId);
      if (detail.videoUrl) {
        setTaskVideoUrls((prev) => ({ ...prev, [taskId]: detail.videoUrl as string }));
      }
    } catch {
      // 结果预取失败不阻断主列表，仅在显式点击时再提示。
    } finally {
      setTaskResultLoadingIds((prev) => ({ ...prev, [taskId]: false }));
    }
  }
```

- [ ] **Step 4: 为可见的完成态任务增加轻量结果预取 effect**

在现有 `filteredTasks` / `selectedTasks` 相关 `useEffect` 后加入：

```tsx
  useEffect(() => {
    filteredTasks.forEach((task) => {
      if (isCompletedTask(task.status) && !taskVideoUrls[task.id] && !taskResultLoadingIds[task.id]) {
        void primeTaskResult(task.id);
      }
    });
  }, [filteredTasks, taskResultLoadingIds, taskVideoUrls]);
```

这个 effect 的边界：

- 只对当前过滤结果里的完成态任务生效
- 不修改后端 summary API
- 不预取失败态或进行中任务详情

- [ ] **Step 5: 增加显式打开结果函数**

在 `openWorkspaceForActiveTask()` 前加入：

```tsx
  async function openTaskResult(taskId: string) {
    const cachedUrl = taskVideoUrls[taskId];
    if (cachedUrl) {
      window.open(cachedUrl, '_blank', 'noopener,noreferrer');
      return;
    }

    setErrorText(null);

    try {
      const detail = await getAgentTask(taskId);
      if (detail.videoUrl) {
        setTaskVideoUrls((prev) => ({ ...prev, [taskId]: detail.videoUrl as string }));
        window.open(detail.videoUrl, '_blank', 'noopener,noreferrer');
        return;
      }
      setErrorText('当前任务还没有可打开的成片，请稍后再试。');
    } catch {
      setErrorText('当前任务结果暂时无法读取，请稍后再试。');
    }
  }
```

- [ ] **Step 6: 运行对应 contract 测试与 build**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_row_actions_include_workspace_and_result_paths
npm run build
```

Expected:

- unittest PASS
- build PASS

- [ ] **Step 7: 提交 helper 与结果缓存基础设施**

Run:

```bash
git add src/components/tasks/TaskManagerPage.tsx
git commit -m "feat: add tasks result access helpers"
```

---

### Task 3: 重写 `/tasks` 列表层文案、行级动作和诚实的控制条

**Files:**
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_operations_console_copy`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_batch_action_is_honest_placeholder`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump tests.test_agent_backend.FrontendClientContractTests.test_tasks_workspace_jump_clears_session_before_setting_active_session tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy tests.test_agent_backend.FrontendClientContractTests.test_tasks_list_rows_do_not_render_active_retry_action`

- [ ] **Step 1: 把页头文案改成任务控制台，而不是“任务管理页面”**

把页头段落：

```tsx
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">任务管理页面</h1>
                <p className="max-w-3xl text-sm leading-6 text-secondary sm:text-base">
                  统一查看任务队列、状态和最近结果；在列表里筛选、搜索、批量理解任务状态，并通过弹窗查看和处理单个任务。
                </p>
```

改成：

```tsx
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">任务控制台</h1>
                <p className="max-w-3xl text-sm leading-6 text-secondary sm:text-base">
                  统一扫读任务状态、最近活动和结果入口；先在列表判断下一步，再按需进入详情弹窗。
                </p>
```

- [ ] **Step 2: 收紧控制条，把批量操作变成诚实的不可用能力**

把当前 `批量操作` 按钮替换成：

```tsx
              <div className="grid gap-2">
                <button
                  type="button"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-slate-100 px-5 text-sm font-semibold text-slate-500"
                  disabled
                >
                  批量操作将在后续阶段开放
                </button>
                <p className="text-xs leading-5 text-secondary">
                  本阶段先支持单任务查看、回到方案和结果直达。
                </p>
              </div>
```

- [ ] **Step 3: 调整列表摘要 chips，强调失败优先关注与结果直达**

把当前第三个 summary chip：

```tsx
            <span className="rounded-full border border-border bg-slate-50 px-3 py-1 text-xs font-semibold text-secondary">
              按更新时间查看
            </span>
```

改成：

```tsx
            <span className="rounded-full border border-border bg-slate-50 px-3 py-1 text-xs font-semibold text-secondary">
              失败优先关注
            </span>
            <span className="rounded-full border border-border bg-slate-50 px-3 py-1 text-xs font-semibold text-secondary">
              结果直达
            </span>
```

- [ ] **Step 4: 重写列表行样式与动作区**

在 `filteredTasks.map(...)` 里做这三处改动：

1. 先在每行顶部定义：

```tsx
                const hasResult = Boolean(taskVideoUrls[task.id]);
                const rowAccentClasses = getTaskRowAccentClasses(task, hasResult);
```

2. 把根容器 `className` 改成：

```tsx
                    className={[
                      'grid gap-3 rounded-lg border p-3 shadow-soft transition lg:grid-cols-[28px_minmax(220px,1.45fr)_110px_130px_minmax(140px,0.9fr)_130px_220px] lg:items-center lg:rounded-none lg:border-x-0 lg:border-b lg:border-t-0 lg:p-3 lg:shadow-none',
                      rowAccentClasses,
                      isSelected ? 'ring-2 ring-lime-200' : 'hover:bg-slate-50/80',
                    ].join(' ')}
```

3. 把操作列从单一 `查看详情` 改成：

```tsx
                    <div className="flex flex-wrap items-center gap-3 lg:justify-end">
                      <button
                        type="button"
                        className="text-xs font-semibold text-ink transition hover:text-slate-600"
                        onClick={() => void openTaskDetail(task.id)}
                      >
                        查看详情
                      </button>
                      <button
                        type="button"
                        className="text-xs font-semibold text-ink transition hover:text-slate-600"
                        onClick={() => {
                          setActiveTask(null);
                          setSession(null);
                          setActiveSessionId(task.sessionId);
                          router.push('/workspace');
                        }}
                      >
                        查看方案
                      </button>
                      {hasResult ? (
                        <button
                          type="button"
                          className="text-xs font-semibold text-emerald-700 transition hover:text-emerald-800"
                          onClick={() => void openTaskResult(task.id)}
                        >
                          打开结果
                        </button>
                      ) : null}
                    </div>
```

这一步的关键是：

- `查看方案` 在行级可直达
- `打开结果` 只在缓存里确认存在 `videoUrl` 时出现
- 不新增任何 active retry 按钮

- [ ] **Step 5: 在任务信息列里增加结果状态辅助文案**

把当前标题下的第二行：

```tsx
                      <span className="text-sm leading-6 text-secondary">
                        {task.sessionId} · 任务 ID {task.id}
                      </span>
```

改成：

```tsx
                      <span className="text-sm leading-6 text-secondary">
                        {task.sessionId} · 任务 ID {task.id}
                      </span>
                      <span className="text-xs leading-5 text-secondary">
                        {hasResult ? '已有成片，可直接打开结果。' : isFailedTask(task.status) ? '任务失败，建议先看详情或回到方案页。' : '继续关注当前阶段推进。'}
                      </span>
```

- [ ] **Step 6: 在 modal 操作区保留现有刷新/查看方案/禁用重新执行逻辑，不引入新 retry 路径**

确认 `结果与操作` section 仍然满足：

- `刷新状态` 按钮保留
- `查看方案` 按钮保留
- 失败态仅显示禁用的 `重新执行`
- `任务级重新执行暂未开放，请返回方案页重新发起。` 文案不变

如果需要调顺顺序，把 `查看方案` 放在 `刷新状态` 后面，但不要把 task-level retry 变成可点击按钮。

- [ ] **Step 7: 运行 `/tasks` 前端 contract 回归**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_operations_console_copy \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_batch_action_is_honest_placeholder \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_modal_actions_wire_refresh_and_workspace_jump \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_workspace_jump_clears_session_before_setting_active_session \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_retry_action_is_disabled_with_guidance_copy \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_list_rows_do_not_render_active_retry_action
```

Expected: PASS

- [ ] **Step 8: 提交列表层运营可用性改动**

Run:

```bash
git add src/components/tasks/TaskManagerPage.tsx tests/test_agent_backend.py
git commit -m "feat: improve tasks operations usability"
```

---

### Task 4: 更新静态页面检查并完成最终验证

**Files:**
- Modify: `scripts/check-product-pages.mjs`
- Test: `npm run build`
- Test: `node scripts/check-product-pages.mjs`
- Test: `/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend`

- [ ] **Step 1: 更新 `/tasks` 静态页面断言**

在 `scripts/check-product-pages.mjs` 中，把 `/tasks` 相关断言：

```js
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '批量操作', 'tasks 页面缺少批量操作入口');
  assertIncludes(tasksHtml, '搜索任务', 'tasks 页面缺少搜索输入');
  assertIncludes(tasksHtml, '可管理任务列表', 'tasks 页面缺少 B1 列表标题');
  assertIncludes(tasksHtml, '查看已选', 'tasks 页面缺少 B1 已选操作入口');
  assertIncludes(tasksHtml, '列表 + 弹窗详情', 'tasks 页面缺少 B1 布局说明');
```

改成：

```js
  assertIncludes(tasksHtml, '任务控制台', 'tasks 页面缺少控制台标题');
  assertIncludes(tasksHtml, '任务列表', 'tasks 页面缺少任务列表区块');
  assertIncludes(tasksHtml, '搜索任务', 'tasks 页面缺少搜索输入');
  assertIncludes(tasksHtml, '可管理任务列表', 'tasks 页面缺少 B1 列表标题');
  assertIncludes(tasksHtml, '查看已选', 'tasks 页面缺少 B1 已选操作入口');
  assertIncludes(tasksHtml, '列表 + 弹窗详情', 'tasks 页面缺少 B1 布局说明');
  assertIncludes(tasksHtml, '批量操作将在后续阶段开放', 'tasks 页面缺少诚实的批量操作提示');
  assertIncludes(tasksHtml, '失败优先关注', 'tasks 页面缺少运营摘要标签');
  assertIncludes(tasksHtml, '结果直达', 'tasks 页面缺少结果摘要标签');
```

- [ ] **Step 2: 运行 build**

Run:

```bash
npm run build
```

Expected: PASS

- [ ] **Step 3: 运行静态产品页检查**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected:

```text
product page checks passed
```

- [ ] **Step 4: 跑完整 `tests.test_agent_backend` 回归**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
```

Expected: PASS（保持当前完整后端/前端 contract 回归不破）

- [ ] **Step 5: 手工验收 `/tasks` 运营控制台**

在本地 dev server 已启动的前提下，手工检查：

1. 打开 `http://127.0.0.1:3002/tasks`（或本次真实端口）
2. 确认页头为 `任务控制台`
3. 确认 `批量操作将在后续阶段开放` 与辅助说明存在
4. 确认失败态任务行比普通行更醒目
5. 确认已完成任务在结果 URL 被缓存后出现 `打开结果`
6. 点击 `查看方案`，确认能跳回 `/workspace`
7. 打开 modal，确认 `刷新状态`、`查看方案` 与禁用 `重新执行` 仍然存在

- [ ] **Step 6: 提交最终检查脚本与收尾**

Run:

```bash
git add scripts/check-product-pages.mjs src/components/tasks/TaskManagerPage.tsx tests/test_agent_backend.py
git commit -m "test: verify tasks operations console"
```

---

## Self-Review

- Spec coverage:
  - B1 结构保持不变：Task 3
  - 列表扫读增强：Task 3
  - 行级 `查看方案` / `打开结果`：Task 2 + Task 3
  - 批量操作诚实降级：Task 3
  - 结果直达与失败可读性：Task 2 + Task 3
  - 静态检查与完整验证：Task 4
- Placeholder scan:
  - 没有使用 `TBD` / `TODO` / “类似 Task N” 之类占位描述
  - 每个代码步骤都给了明确代码或替换片段
- Type consistency:
  - 只使用现有 `AgentTaskSummary`、`AgentTaskDetail`
  - 新增状态名 `taskVideoUrls`、`taskResultLoadingIds`、`openTaskResult()` 在后续任务里保持一致

---

Plan complete and saved to `docs/superpowers/plans/2026-05-07-tasks-operations-usability-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
