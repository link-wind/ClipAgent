# Product Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved ClipForge Product Workspace with a dashboard home page, a single-column brief conversation page, and a manageable task list page with modal details.

**Architecture:** Keep the current Next.js App Router, React, Zustand, and CSS Modules stack for this pass. Split the current single `AgentWorkspace` homepage into focused route-level pages, add a shared product shell/design token layer, and add only the minimum backend read APIs needed for dashboard and task management data. Tailwind is not introduced in this implementation; evaluate a gradual migration after the three product pages are stable.

**Tech Stack:** Next.js 14, React 18, TypeScript, Zustand, CSS Modules, FastAPI, SQLAlchemy, existing Agent session/job tables, existing Python `unittest` backend tests.

---

## Scope Notes

The approved design is broader than a visual skin. The frontend can render the three pages immediately, but the dashboard and task manager need read-oriented data that the backend does not currently expose.

This plan therefore has two layers:

1. **Frontend product workspace:** route shell, dashboard, single-column workspace, task list and modal.
2. **Minimal backend reads:** list recent sessions/tasks and read task detail from existing persisted Agent data.

No Tailwind migration is included in this plan. The implementation should keep CSS Modules so the information architecture change remains the main risk.

## File Structure

- Create `src/components/layout/ProductShell.tsx`
  - Owns the left navigation rail, top-level page frame, active nav state, and common page width behavior.
- Create `src/components/layout/ProductShell.module.css`
  - Owns shared product layout styling.
- Modify `src/app/globals.css`
  - Adds the approved Product Workspace tokens and base page styling.
- Modify `src/app/page.tsx`
  - Renders the dashboard instead of the old Agent workspace.
- Create `src/app/workspace/page.tsx`
  - Renders the single-column brief conversation workspace.
- Create `src/app/tasks/page.tsx`
  - Renders the task manager page.
- Create `src/components/dashboard/DashboardPage.tsx`
  - Owns dashboard content composition.
- Create `src/components/dashboard/DashboardPage.module.css`
  - Owns dashboard visual layout, metrics, charts, recent projects, and sidebar cards.
- Create `src/components/workspace/BriefWorkspacePage.tsx`
  - Owns the single-column conversation page wrapper.
- Create `src/components/workspace/BriefWorkspacePage.module.css`
  - Owns single-column conversation layout.
- Create `src/components/workspace/AiStepFlow.tsx`
  - Renders AI step progress first, then step result.
- Create `src/components/workspace/AiStepFlow.module.css`
  - Owns step progress/result styling.
- Modify `src/components/agent/AgentChat.tsx`
  - Keeps raw user prompt display, composer behavior, and confirm action.
- Modify `src/components/agent/AgentChat.module.css`
  - Restyles chat bubbles and composer for the single-column page.
- Create `src/components/tasks/TaskManagerPage.tsx`
  - Owns task toolbar, list selection, filters, and modal open state.
- Create `src/components/tasks/TaskManagerPage.module.css`
  - Owns task list and modal styling.
- Create `src/lib/taskApi.ts`
  - Fetches task list and task detail from new backend endpoints.
- Modify `backend/models/agent.py`
  - Adds read response models for dashboard summaries and agent task summaries.
- Modify `backend/db/repositories/agent_sessions.py`
  - Adds recent-session list query.
- Modify `backend/db/repositories/agent_jobs.py`
  - Adds job list/detail query methods.
- Create `backend/services/agent_task_read_service.py`
  - Builds task list and task detail responses from existing session, plan, job, event, and artifact rows.
- Modify `backend/api/agent.py`
  - Adds `GET /api/agent/dashboard`, `GET /api/agent/tasks`, and `GET /api/agent/tasks/{job_id}`.
- Modify `tests/test_agent_api_p0.py`
  - Adds API contract tests for dashboard, task list, and task detail.

---

### Task 1: Add Backend Read Models For Dashboard And Tasks

**Files:**
- Modify: `backend/models/agent.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Add model contract tests**

Append these tests to `AgentApiP0ContractTests` in `tests/test_agent_api_p0.py`:

```python
    def test_agent_dashboard_and_task_response_models_can_be_instantiated(self):
        from backend.models.agent import AgentDashboardSummary, AgentTaskDetail, AgentTaskSummary

        task = AgentTaskSummary(
            id="job-1",
            sessionId="session-1",
            title="AI 笔记产品宣传片",
            status="queued",
            progress=25,
            currentStep="任务已入队",
            createdAt="2026-05-04T12:00:00",
            updatedAt="2026-05-04T12:01:00",
        )
        detail = AgentTaskDetail(
            **task.model_dump(),
            events=[],
            clips=[],
            error=None,
            videoUrl=None,
        )
        dashboard = AgentDashboardSummary(
            totalSessions=1,
            activeTasks=1,
            completedTasks=0,
            failedTasks=0,
            recentTasks=[task],
        )

        self.assertEqual(task.title, "AI 笔记产品宣传片")
        self.assertEqual(detail.id, "job-1")
        self.assertEqual(dashboard.activeTasks, 1)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_dashboard_and_task_response_models_can_be_instantiated
```

Expected: fail with `ImportError` because `AgentDashboardSummary`, `AgentTaskDetail`, and `AgentTaskSummary` do not exist yet.

- [ ] **Step 3: Add read response models**

In `backend/models/agent.py`, add these models after `AgentSession`:

```python
class AgentTaskSummary(BaseModel):
    id: str
    sessionId: str
    title: str
    status: str
    progress: float = 0.0
    currentStep: str = ""
    createdAt: str
    updatedAt: str


class AgentTaskDetail(AgentTaskSummary):
    events: List[AgentEvent] = Field(default_factory=list)
    clips: List[ClipInfo] = Field(default_factory=list)
    error: Optional[AgentError] = None
    videoUrl: Optional[str] = None


class AgentDashboardSummary(BaseModel):
    totalSessions: int = 0
    activeTasks: int = 0
    completedTasks: int = 0
    failedTasks: int = 0
    recentTasks: List[AgentTaskSummary] = Field(default_factory=list)
```

- [ ] **Step 4: Run the focused test and confirm it passes**

Run:

```bash
python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_dashboard_and_task_response_models_can_be_instantiated
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add backend/models/agent.py tests/test_agent_api_p0.py
git commit -m "feat: add agent dashboard task response models"
```

---

### Task 2: Add Backend Task And Dashboard Read APIs

**Files:**
- Modify: `backend/db/repositories/agent_sessions.py`
- Modify: `backend/db/repositories/agent_jobs.py`
- Create: `backend/services/agent_task_read_service.py`
- Modify: `backend/api/agent.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Add API contract tests**

Append this test to `AgentApiP0ContractTests` in `tests/test_agent_api_p0.py`:

```python
    def test_agent_dashboard_task_list_and_detail_endpoints_return_persisted_jobs(self):
        async def _run():
            session = self.session_service.create_session("做一个 30 秒产品宣传片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="queued",
                    progress=25,
                    current_step="任务已入队",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_queued",
                    step="queued",
                    progress=25,
                    message="任务已入队，等待执行",
                    payload_json={"jobId": job_record.id},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                dashboard_response = await client.get("/api/agent/dashboard")
                self.assertEqual(dashboard_response.status_code, 200)
                dashboard = dashboard_response.json()
                self.assertEqual(dashboard["totalSessions"], 1)
                self.assertEqual(dashboard["activeTasks"], 1)
                self.assertEqual(dashboard["recentTasks"][0]["id"], job_id)

                list_response = await client.get("/api/agent/tasks")
                self.assertEqual(list_response.status_code, 200)
                tasks = list_response.json()
                self.assertEqual(len(tasks), 1)
                self.assertEqual(tasks[0]["id"], job_id)
                self.assertEqual(tasks[0]["sessionId"], session.id)
                self.assertEqual(tasks[0]["status"], "queued")

                detail_response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail = detail_response.json()
                self.assertEqual(detail["id"], job_id)
                self.assertEqual(detail["events"][0]["eventType"], "job_queued")

        import asyncio

        from backend.services.agent_task_read_service import AgentTaskReadService

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ), patch.object(
            agent_api_module,
            "task_read_service",
            task_read_service,
        ):
            asyncio.run(_run())
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run:

```bash
python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_dashboard_task_list_and_detail_endpoints_return_persisted_jobs
```

Expected: fail because `backend.services.agent_task_read_service` and the new API routes do not exist yet.

- [ ] **Step 3: Add repository list methods**

In `backend/db/repositories/agent_sessions.py`, add:

```python
    def list_recent(self, limit: int = 20) -> list[AgentSessionRecord]:
        stmt = (
            select(AgentSessionRecord)
            .order_by(AgentSessionRecord.updated_at.desc(), AgentSessionRecord.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
```

Ensure the file imports `select`:

```python
from sqlalchemy import select
```

In `backend/db/repositories/agent_jobs.py`, add:

```python
    def list_recent(self, limit: int = 50) -> list[AgentJobRecord]:
        stmt = (
            select(AgentJobRecord)
            .order_by(AgentJobRecord.updated_at.desc(), AgentJobRecord.id.asc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt))
```

Ensure the file imports `select`:

```python
from sqlalchemy import select
```

- [ ] **Step 4: Create task read service**

Create `backend/services/agent_task_read_service.py`:

```python
from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentJobRepository,
    AgentSessionRepository,
)
from backend.models.agent import (
    AgentDashboardSummary,
    AgentError,
    AgentTaskDetail,
    AgentTaskSummary,
)
from backend.services.agent_read_service import AgentReadService


RUNNING_JOB_STATUSES = {"queued", "searching", "downloading", "rendering", "pending"}


class AgentTaskReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.read_service = AgentReadService(session_factory=session_factory)

    def list_tasks(self, limit: int = 50) -> list[AgentTaskSummary]:
        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            session_repo = AgentSessionRepository(db)
            return [
                self._build_task_summary(job, session_repo.get(job.session_id) if job.session_id else None)
                for job in job_repo.list_recent(limit=limit)
            ]

    def read_task(self, job_id: str) -> AgentTaskDetail:
        with self.session_factory() as db:
            job = AgentJobRepository(db).get(job_id)
            if job is None:
                raise KeyError(job_id)

            session = AgentSessionRepository(db).get(job.session_id) if job.session_id else None
            events = AgentEventRepository(db).list_for_session(job.session_id) if job.session_id else []
            artifacts = AgentArtifactRepository(db).list_for_session(job.session_id) if job.session_id else []
            clips = [
                self.read_service._build_clip_info(row)
                for row in artifacts
                if row.artifact_type == "clip"
            ]
            summary = self._build_task_summary(job, session)
            return AgentTaskDetail(
                **summary.model_dump(),
                events=self.read_service.build_event_response(events),
                clips=clips,
                error=(
                    AgentError(message=job.error_message)
                    if job.error_message
                    else None
                ),
                videoUrl=session.video_url if session is not None else None,
            )

    def read_dashboard(self) -> AgentDashboardSummary:
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            job_repo = AgentJobRepository(db)
            sessions = session_repo.list_recent(limit=200)
            jobs = job_repo.list_recent(limit=50)
            recent_tasks = [
                self._build_task_summary(job, session_repo.get(job.session_id) if job.session_id else None)
                for job in jobs[:6]
            ]
            return AgentDashboardSummary(
                totalSessions=len(sessions),
                activeTasks=sum(1 for job in jobs if job.status in RUNNING_JOB_STATUSES),
                completedTasks=sum(1 for job in jobs if job.status == "done"),
                failedTasks=sum(1 for job in jobs if job.status == "failed"),
                recentTasks=recent_tasks,
            )

    def _build_task_summary(self, job, session) -> AgentTaskSummary:
        title = session.title if session is not None and session.title else "未命名视频任务"
        return AgentTaskSummary(
            id=job.id,
            sessionId=job.session_id or "",
            title=title,
            status=job.status,
            progress=job.progress,
            currentStep=job.current_step or "",
            createdAt=job.created_at.isoformat(),
            updatedAt=job.updated_at.isoformat(),
        )
```

- [ ] **Step 5: Wire API routes**

In `backend/api/agent.py`, update imports:

```python
from backend.models.agent import AgentDashboardSummary, AgentEvent, AgentSession, AgentTaskDetail, AgentTaskSummary
from backend.services.agent_task_read_service import AgentTaskReadService
```

Create the service singleton near the existing services:

```python
task_read_service = AgentTaskReadService(session_factory=SessionLocal)
```

Add routes after the session routes:

```python
@router.get("/dashboard", response_model=AgentDashboardSummary)
async def get_dashboard():
    return task_read_service.read_dashboard()


@router.get("/tasks", response_model=list[AgentTaskSummary])
async def list_tasks():
    return task_read_service.list_tasks()


@router.get("/tasks/{job_id}", response_model=AgentTaskDetail)
async def get_task(job_id: str):
    try:
        return task_read_service.read_task(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Task not found")
```

- [ ] **Step 6: Run focused backend test**

Run:

```bash
python -m unittest tests.test_agent_api_p0.AgentApiP0ContractTests.test_agent_dashboard_task_list_and_detail_endpoints_return_persisted_jobs
```

Expected: pass.

- [ ] **Step 7: Run backend API test file**

Run:

```bash
python -m unittest tests.test_agent_api_p0
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add backend/db/repositories/agent_sessions.py backend/db/repositories/agent_jobs.py backend/services/agent_task_read_service.py backend/api/agent.py tests/test_agent_api_p0.py
git commit -m "feat: expose agent dashboard and task reads"
```

---

### Task 3: Add Frontend API Types For Dashboard And Tasks

**Files:**
- Create: `src/lib/taskApi.ts`
- Modify: `src/lib/agentApi.ts`

- [ ] **Step 1: Create task API client**

Create `src/lib/taskApi.ts`:

```ts
import type { AgentEvent, ClipInfo } from './agentApi';

export interface AgentTaskSummary {
  id: string;
  sessionId: string;
  title: string;
  status: string;
  progress: number;
  currentStep: string;
  createdAt: string;
  updatedAt: string;
}

export interface AgentTaskDetail extends AgentTaskSummary {
  events: AgentEvent[];
  clips: ClipInfo[];
  error: { message: string; retryableStep?: string | null } | null;
  videoUrl: string | null;
}

export interface AgentDashboardSummary {
  totalSessions: number;
  activeTasks: number;
  completedTasks: number;
  failedTasks: number;
  recentTasks: AgentTaskSummary[];
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`请求失败：${response.status} ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function getAgentDashboard(): Promise<AgentDashboardSummary> {
  return request<AgentDashboardSummary>('/api/agent/dashboard');
}

export function listAgentTasks(): Promise<AgentTaskSummary[]> {
  return request<AgentTaskSummary[]>('/api/agent/tasks');
}

export function getAgentTask(jobId: string): Promise<AgentTaskDetail> {
  return request<AgentTaskDetail>(`/api/agent/tasks/${encodeURIComponent(jobId)}`);
}
```

- [ ] **Step 2: Build-check TypeScript**

Run:

```bash
npm run build
```

Expected: pass with no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/taskApi.ts
git commit -m "feat: add frontend task read api client"
```

---

### Task 4: Add Shared Product Shell And Tokens

**Files:**
- Create: `src/components/layout/ProductShell.tsx`
- Create: `src/components/layout/ProductShell.module.css`
- Modify: `src/app/globals.css`

- [ ] **Step 1: Create shell component**

Create `src/components/layout/ProductShell.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import styles from './ProductShell.module.css';

const NAV_ITEMS = [
  { href: '/', label: '总览', shortLabel: 'D' },
  { href: '/workspace', label: '方案', shortLabel: 'W' },
  { href: '/tasks', label: '任务', shortLabel: 'T' },
];

export default function ProductShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className={styles.shell}>
      <aside className={styles.rail} aria-label="主导航">
        <Link href="/" className={styles.logo} aria-label="ClipForge 首页">
          C
        </Link>
        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => {
            const isActive = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.navItem} ${isActive ? styles.active : ''}`}
                title={item.label}
              >
                <span>{item.shortLabel}</span>
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Create shell CSS**

Create `src/components/layout/ProductShell.module.css`:

```css
.shell {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  background: var(--page-bg);
  color: var(--text-primary);
}

.rail {
  position: sticky;
  top: 0;
  height: 100vh;
  background: var(--ink);
  padding: 18px 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 18px;
}

.logo,
.navItem {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: grid;
  place-items: center;
  text-decoration: none;
  font-weight: 900;
}

.logo {
  background: var(--accent);
  color: var(--ink);
}

.nav {
  display: grid;
  gap: 12px;
}

.navItem {
  color: var(--rail-text);
  background: rgba(255, 255, 255, 0.06);
}

.navItem.active {
  color: var(--ink);
  background: var(--accent);
}

.main {
  min-width: 0;
  padding: 22px 26px 30px;
}

@media (max-width: 760px) {
  .shell {
    grid-template-columns: 1fr;
  }

  .rail {
    position: static;
    height: auto;
    min-height: 64px;
    padding: 12px 14px;
    flex-direction: row;
    justify-content: space-between;
  }

  .nav {
    grid-auto-flow: column;
  }

  .main {
    padding: 18px 14px 24px;
  }
}
```

- [ ] **Step 3: Update global tokens**

Replace the `:root` block in `src/app/globals.css` with:

```css
:root {
  --page-bg: #f4f5f3;
  --surface: #ffffff;
  --surface-subtle: #f7f9f6;
  --surface-muted: #eef2ed;
  --ink: #1f2522;
  --text-primary: #1f2522;
  --text-secondary: #68736c;
  --text-muted: #7b847d;
  --rail-text: #c8d0c8;
  --border: #dfe4df;
  --border-soft: #e8ebe7;
  --accent: #a8c66c;
  --accent-strong: #6da7a2;
  --accent-ink: #365314;
  --danger: #991b1b;
  --danger-bg: #fee2e2;
  --info: #1d4ed8;
  --info-bg: #dbeafe;
  --shadow-soft: 0 10px 28px rgba(32, 37, 34, 0.045);
  --radius-sm: 4px;
  --radius-md: 8px;
}
```

Replace the `body` rule with:

```css
body {
  background: var(--page-bg);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  letter-spacing: 0;
  overflow: auto;
}
```

- [ ] **Step 4: Build-check shell**

Run:

```bash
npm run build
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/components/layout/ProductShell.tsx src/components/layout/ProductShell.module.css src/app/globals.css
git commit -m "feat: add product workspace shell"
```

---

### Task 5: Build Dashboard Home Page

**Files:**
- Modify: `src/app/page.tsx`
- Create: `src/components/dashboard/DashboardPage.tsx`
- Create: `src/components/dashboard/DashboardPage.module.css`

- [ ] **Step 1: Create dashboard component**

Create `src/components/dashboard/DashboardPage.tsx`:

```tsx
'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentDashboard, type AgentDashboardSummary } from '@/lib/taskApi';
import styles from './DashboardPage.module.css';

const FALLBACK_DASHBOARD: AgentDashboardSummary = {
  totalSessions: 0,
  activeTasks: 0,
  completedTasks: 0,
  failedTasks: 0,
  recentTasks: [],
};

const TREND_VALUES = [42, 58, 36, 74, 51, 82, 68];

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<AgentDashboardSummary>(FALLBACK_DASHBOARD);
  const [errorText, setErrorText] = useState('');

  useEffect(() => {
    let isActive = true;
    getAgentDashboard()
      .then((nextDashboard) => {
        if (isActive) {
          setDashboard(nextDashboard);
          setErrorText('');
        }
      })
      .catch((error: unknown) => {
        if (isActive) {
          setErrorText(error instanceof Error ? error.message : '数据加载失败');
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  const completionRate = useMemo(() => {
    const total = dashboard.completedTasks + dashboard.failedTasks + dashboard.activeTasks;
    return total > 0 ? Math.round((dashboard.completedTasks / total) * 100) : 0;
  }, [dashboard]);

  return (
    <ProductShell>
      <div className={styles.page}>
        <header className={styles.top}>
          <div>
            <p className={styles.crumb}>ClipForge / 总览</p>
            <h1>项目数据总览</h1>
          </div>
          <div className={styles.topActions}>
            <input className={styles.search} aria-label="搜索项目或任务" placeholder="搜索项目、任务、会话" />
            <Link className={styles.primaryAction} href="/workspace">
              新建方案
            </Link>
          </div>
        </header>

        {errorText ? <p className={styles.error}>{errorText}</p> : null}

        <section className={styles.stats} aria-label="关键指标">
          <Metric label="会话总数" value={dashboard.totalSessions} hint="累计方案沟通" />
          <Metric label="运行任务" value={dashboard.activeTasks} hint="正在处理" />
          <Metric label="完成任务" value={dashboard.completedTasks} hint="已产出视频" />
          <Metric label="完成率" value={`${completionRate}%`} hint="按当前任务统计" />
        </section>

        <div className={styles.grid}>
          <section className={styles.card}>
            <div className={styles.panelHead}>
              <h2>生产趋势</h2>
              <span>最近 7 天</span>
            </div>
            <div className={styles.chart} aria-label="最近 7 天生产趋势">
              {TREND_VALUES.map((value, index) => (
                <span key={index} className={styles.bar} style={{ height: `${value}%` }} />
              ))}
            </div>
            <div className={styles.days}>
              <span>Mon</span>
              <span>Tue</span>
              <span>Wed</span>
              <span>Thu</span>
              <span>Fri</span>
              <span>Sat</span>
              <span>Sun</span>
            </div>
          </section>

          <section className={styles.card}>
            <div className={styles.panelHead}>
              <h2>资产构成</h2>
              <span>当前工作区</span>
            </div>
            <div className={styles.assetMix}>
              <div className={styles.ring} aria-label="资产构成评分">86</div>
              <div className={styles.legend}>
                <Legend color="ink" label="成片" value={`${dashboard.completedTasks} 个`} />
                <Legend color="teal" label="运行中" value={`${dashboard.activeTasks} 个`} />
                <Legend color="green" label="会话" value={`${dashboard.totalSessions} 个`} />
              </div>
            </div>
          </section>

          <section className={`${styles.card} ${styles.recent}`}>
            <div className={styles.panelHead}>
              <h2>最近任务</h2>
              <Link href="/tasks">查看全部</Link>
            </div>
            <div className={styles.taskList}>
              {dashboard.recentTasks.length ? (
                dashboard.recentTasks.map((task) => (
                  <Link key={task.id} className={styles.taskRow} href="/tasks">
                    <span>
                      <strong>{task.title}</strong>
                      <small>{task.currentStep || '等待更新'}</small>
                    </span>
                    <em>{task.progress}%</em>
                  </Link>
                ))
              ) : (
                <p className={styles.empty}>暂无任务，先进入方案页创建一个新项目。</p>
              )}
            </div>
          </section>
        </div>
      </div>
    </ProductShell>
  );
}

function Metric({ label, value, hint }: { label: string; value: number | string; hint: string }) {
  return (
    <article className={styles.metric}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </article>
  );
}

function Legend({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <div className={styles.legendItem}>
      <i className={styles[color]} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
```

- [ ] **Step 2: Create dashboard CSS**

Create `src/components/dashboard/DashboardPage.module.css` using the approved C direction:

```css
.page {
  display: grid;
  gap: 18px;
}

.top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
}

.crumb {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}

.top h1 {
  font-size: 26px;
  line-height: 1.15;
}

.topActions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search {
  width: 280px;
  min-height: 40px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface);
  color: var(--text-primary);
  padding: 10px 12px;
}

.primaryAction {
  min-height: 40px;
  border-radius: var(--radius-md);
  background: var(--ink);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 14px;
  text-decoration: none;
  font-weight: 850;
}

.error {
  border: 1px solid var(--danger-bg);
  background: #fff7f7;
  color: var(--danger);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric,
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-soft);
}

.metric {
  min-height: 112px;
  padding: 15px;
  display: grid;
  align-content: space-between;
}

.metric span,
.metric small {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.metric strong {
  font-size: 30px;
  line-height: 1;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
  gap: 16px;
  align-items: start;
}

.panelHead {
  min-height: 54px;
  border-bottom: 1px solid var(--border-soft);
  padding: 0 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panelHead h2 {
  font-size: 16px;
}

.panelHead span,
.panelHead a {
  color: var(--text-secondary);
  font-size: 13px;
  text-decoration: none;
}

.chart {
  height: 236px;
  padding: 18px 16px 0;
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 10px;
  align-items: end;
}

.bar {
  min-height: 30px;
  border-radius: 8px 8px 4px 4px;
  background: linear-gradient(180deg, #6da7a2, #376c68);
}

.bar:nth-child(odd) {
  background: linear-gradient(180deg, #395b64, #20343a);
}

.bar:last-child {
  background: linear-gradient(180deg, #c3d7a4, #789561);
}

.days {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 10px;
  color: var(--text-muted);
  font-size: 12px;
  text-align: center;
  padding: 10px 16px 16px;
}

.assetMix {
  padding: 18px 16px;
  display: grid;
  grid-template-columns: 132px 1fr;
  gap: 16px;
  align-items: center;
}

.ring {
  width: 132px;
  height: 132px;
  border-radius: 50%;
  background: conic-gradient(#20343a 0 44%, #6da7a2 44% 72%, #c3d7a4 72% 100%);
  display: grid;
  place-items: center;
  color: var(--ink);
  font-size: 28px;
  font-weight: 900;
  position: relative;
}

.ring::before {
  content: "";
  position: absolute;
  inset: 18px;
  border-radius: 50%;
  background: var(--surface);
}

.ring {
  isolation: isolate;
}

.ring::after {
  content: "86";
  z-index: 1;
}

.legend {
  display: grid;
  gap: 10px;
}

.legendItem {
  display: grid;
  grid-template-columns: 12px 1fr auto;
  gap: 9px;
  align-items: center;
  font-size: 13px;
}

.legendItem i {
  width: 12px;
  height: 12px;
  border-radius: 3px;
}

.ink {
  background: #20343a;
}

.teal {
  background: #6da7a2;
}

.green {
  background: #c3d7a4;
}

.recent {
  grid-column: 1 / -1;
}

.taskList {
  padding: 6px 16px 16px;
  display: grid;
}

.taskRow {
  min-height: 64px;
  border-bottom: 1px solid var(--border-soft);
  color: inherit;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  text-decoration: none;
}

.taskRow:last-child {
  border-bottom: 0;
}

.taskRow strong,
.taskRow small {
  display: block;
}

.taskRow small,
.empty {
  color: var(--text-secondary);
  font-size: 12px;
}

.taskRow em {
  color: var(--accent-ink);
  font-style: normal;
  font-weight: 900;
}

@media (max-width: 980px) {
  .top {
    align-items: flex-start;
    flex-direction: column;
  }

  .stats,
  .grid {
    grid-template-columns: 1fr;
  }

  .search {
    width: min(100%, 320px);
  }
}
```

- [ ] **Step 3: Route homepage to dashboard**

Replace `src/app/page.tsx` with:

```tsx
import DashboardPage from '@/components/dashboard/DashboardPage';

export default function HomePage() {
  return <DashboardPage />;
}
```

- [ ] **Step 4: Build-check dashboard**

Run:

```bash
npm run build
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/app/page.tsx src/components/dashboard/DashboardPage.tsx src/components/dashboard/DashboardPage.module.css
git commit -m "feat: add product dashboard page"
```

---

### Task 6: Build Single-Column Brief Conversation Workspace

**Files:**
- Create: `src/app/workspace/page.tsx`
- Create: `src/components/workspace/BriefWorkspacePage.tsx`
- Create: `src/components/workspace/BriefWorkspacePage.module.css`
- Create: `src/components/workspace/AiStepFlow.tsx`
- Create: `src/components/workspace/AiStepFlow.module.css`
- Modify: `src/components/agent/AgentChat.tsx`
- Modify: `src/components/agent/AgentChat.module.css`

- [ ] **Step 1: Create AI step flow component**

Create `src/components/workspace/AiStepFlow.tsx`:

```tsx
import styles from './AiStepFlow.module.css';

const STEPS = [
  {
    title: '理解原始需求',
    progress: 100,
    result: '保留用户原始 prompt，AI 单独提炼目标、受众、风格和交付格式。',
  },
  {
    title: '生成方案方向',
    progress: 100,
    result: '提供多个可选方向，让用户先确认主创意路线。',
  },
  {
    title: '确认最终方案',
    progress: 68,
    result: '基于已选择方向整理最终执行方案，确认后生成任务。',
  },
];

export default function AiStepFlow() {
  return (
    <section className={styles.flow} aria-label="AI 分析步骤">
      {STEPS.map((step) => (
        <article key={step.title} className={styles.step}>
          <div className={styles.head}>
            <strong>{step.title}</strong>
            <span>{step.progress}%</span>
          </div>
          <div className={styles.track} aria-label={`${step.title}进度`}>
            <span style={{ width: `${step.progress}%` }} />
          </div>
          <p>{step.result}</p>
        </article>
      ))}
    </section>
  );
}
```

- [ ] **Step 2: Create AI step flow CSS**

Create `src/components/workspace/AiStepFlow.module.css`:

```css
.flow {
  display: grid;
  gap: 12px;
}

.step {
  border: 1px solid var(--border);
  background: var(--surface);
  border-radius: var(--radius-md);
  padding: 12px;
  display: grid;
  gap: 10px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.head strong {
  font-size: 14px;
}

.head span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.track {
  height: 8px;
  background: var(--surface-muted);
  border-radius: 999px;
  overflow: hidden;
}

.track span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--accent-strong), var(--accent));
}

.step p {
  color: var(--text-secondary);
  line-height: 1.55;
  margin: 0;
}
```

- [ ] **Step 3: Create workspace page component**

Create `src/components/workspace/BriefWorkspacePage.tsx`:

```tsx
'use client';

import ProductShell from '@/components/layout/ProductShell';
import AgentChat from '@/components/agent/AgentChat';
import AiStepFlow from './AiStepFlow';
import styles from './BriefWorkspacePage.module.css';

export default function BriefWorkspacePage() {
  return (
    <ProductShell>
      <div className={styles.page}>
        <header className={styles.top}>
          <div>
            <p className={styles.crumb}>ClipForge / 方案沟通</p>
            <h1>从需求到执行方案</h1>
          </div>
          <span className={styles.status}>等待确认</span>
        </header>

        <section className={styles.workspace} aria-label="方案沟通工作区">
          <AgentChat />
          <AiStepFlow />
        </section>
      </div>
    </ProductShell>
  );
}
```

- [ ] **Step 4: Create workspace CSS**

Create `src/components/workspace/BriefWorkspacePage.module.css`:

```css
.page {
  width: min(980px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.top {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
}

.crumb {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 6px;
}

.top h1 {
  font-size: 26px;
  line-height: 1.15;
}

.status {
  border-radius: 999px;
  background: #e3efd4;
  color: var(--accent-ink);
  padding: 8px 11px;
  font-size: 13px;
  font-weight: 850;
}

.workspace {
  display: grid;
  gap: 14px;
}

@media (max-width: 680px) {
  .top {
    align-items: flex-start;
    flex-direction: column;
  }
}
```

- [ ] **Step 5: Create route**

Create `src/app/workspace/page.tsx`:

```tsx
import BriefWorkspacePage from '@/components/workspace/BriefWorkspacePage';

export default function WorkspacePage() {
  return <BriefWorkspacePage />;
}
```

- [ ] **Step 6: Update chat copy to preserve raw user prompt**

In `src/components/agent/AgentChat.tsx`, keep message rendering as `item.content` only. Update the empty state copy to:

```tsx
<div className={styles.empty}>
  <h2>描述你想完成的视频</h2>
  <p>直接说你的想法即可，目标、格式、风格和执行拆分会由 AI 在后续步骤里提炼。</p>
</div>
```

- [ ] **Step 7: Build-check workspace**

Run:

```bash
npm run build
```

Expected: pass.

- [ ] **Step 8: Commit**

```bash
git add src/app/workspace/page.tsx src/components/workspace/BriefWorkspacePage.tsx src/components/workspace/BriefWorkspacePage.module.css src/components/workspace/AiStepFlow.tsx src/components/workspace/AiStepFlow.module.css src/components/agent/AgentChat.tsx src/components/agent/AgentChat.module.css
git commit -m "feat: add single column brief workspace"
```

---

### Task 7: Build Task Manager With Modal Detail

**Files:**
- Create: `src/app/tasks/page.tsx`
- Create: `src/components/tasks/TaskManagerPage.tsx`
- Create: `src/components/tasks/TaskManagerPage.module.css`

- [ ] **Step 1: Create task manager component**

Create `src/components/tasks/TaskManagerPage.tsx`:

```tsx
'use client';

import { useEffect, useMemo, useState } from 'react';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentTask, listAgentTasks, type AgentTaskDetail, type AgentTaskSummary } from '@/lib/taskApi';
import styles from './TaskManagerPage.module.css';

const FILTERS = ['全部', '运行中', '已完成', '失败'];

export default function TaskManagerPage() {
  const [tasks, setTasks] = useState<AgentTaskSummary[]>([]);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('全部');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeTask, setActiveTask] = useState<AgentTaskDetail | null>(null);
  const [errorText, setErrorText] = useState('');

  useEffect(() => {
    let isActive = true;
    listAgentTasks()
      .then((nextTasks) => {
        if (isActive) {
          setTasks(nextTasks);
          setErrorText('');
        }
      })
      .catch((error: unknown) => {
        if (isActive) {
          setErrorText(error instanceof Error ? error.message : '任务加载失败');
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  const visibleTasks = useMemo(() => {
    return tasks.filter((task) => {
      const matchesQuery = task.title.toLowerCase().includes(query.trim().toLowerCase());
      const matchesFilter =
        filter === '全部' ||
        (filter === '运行中' && ['queued', 'searching', 'downloading', 'rendering', 'pending'].includes(task.status)) ||
        (filter === '已完成' && task.status === 'done') ||
        (filter === '失败' && task.status === 'failed');
      return matchesQuery && matchesFilter;
    });
  }, [filter, query, tasks]);

  const openTask = async (taskId: string) => {
    const detail = await getAgentTask(taskId);
    setActiveTask(detail);
  };

  const toggleSelected = (taskId: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(taskId)) {
        next.delete(taskId);
      } else {
        next.add(taskId);
      }
      return next;
    });
  };

  return (
    <ProductShell>
      <div className={styles.page}>
        <header className={styles.top}>
          <div>
            <p className={styles.crumb}>ClipForge / 任务</p>
            <h1>任务管理</h1>
          </div>
          <input
            className={styles.search}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索任务"
            aria-label="搜索任务"
          />
        </header>

        {errorText ? <p className={styles.error}>{errorText}</p> : null}

        <section className={styles.board}>
          <div className={styles.toolbar}>
            <span>{selectedIds.size ? `已选 ${selectedIds.size} 个任务` : `${visibleTasks.length} 个任务`}</span>
            <div className={styles.filters}>
              {FILTERS.map((item) => (
                <button
                  key={item}
                  className={`${styles.chip} ${filter === item ? styles.active : ''}`}
                  type="button"
                  onClick={() => setFilter(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.tableHead}>
            <span />
            <span>任务</span>
            <span>状态</span>
            <span>进度</span>
            <span>更新时间</span>
            <span />
          </div>

          <div className={styles.rows}>
            {visibleTasks.map((task) => (
              <article key={task.id} className={styles.row}>
                <button
                  className={`${styles.check} ${selectedIds.has(task.id) ? styles.checked : ''}`}
                  type="button"
                  aria-label={`选择 ${task.title}`}
                  onClick={() => toggleSelected(task.id)}
                />
                <div className={styles.title}>
                  <strong>{task.title}</strong>
                  <span>{task.currentStep || '等待更新'}</span>
                </div>
                <StatusBadge status={task.status} />
                <div className={styles.progress}>
                  <span>{task.progress}%</span>
                  <i><b style={{ width: `${task.progress}%` }} /></i>
                </div>
                <time>{new Date(task.updatedAt).toLocaleString('zh-CN')}</time>
                <button className={styles.linkBtn} type="button" onClick={() => void openTask(task.id)}>
                  详情
                </button>
              </article>
            ))}
          </div>
        </section>

        {activeTask ? <TaskModal task={activeTask} onClose={() => setActiveTask(null)} /> : null}
      </div>
    </ProductShell>
  );
}

function StatusBadge({ status }: { status: string }) {
  const label = status === 'done' ? '完成' : status === 'failed' ? '失败' : '运行中';
  return <span className={`${styles.badge} ${styles[status] || styles.running}`}>{label}</span>;
}

function TaskModal({ task, onClose }: { task: AgentTaskDetail; onClose: () => void }) {
  return (
    <div className={styles.modalLayer} role="dialog" aria-modal="true" aria-label="任务详情">
      <section className={styles.modal}>
        <header className={styles.modalHead}>
          <div>
            <h2>{task.title}</h2>
            <p>{task.currentStep || '等待更新'}</p>
          </div>
          <button className={styles.close} type="button" onClick={onClose} aria-label="关闭详情">
            ×
          </button>
        </header>
        <div className={styles.modalBody}>
          <div className={styles.summary}>
            <Metric label="状态" value={task.status} />
            <Metric label="进度" value={`${task.progress}%`} />
            <Metric label="片段" value={`${task.clips.length}`} />
            <Metric label="事件" value={`${task.events.length}`} />
          </div>
          {task.error ? <p className={styles.error}>{task.error.message}</p> : null}
          <div className={styles.timeline}>
            {task.events.map((event) => (
              <article key={event.id} className={styles.event}>
                <strong>{event.message || event.eventType}</strong>
                <span>{event.step || 'system'} · {event.progress ?? 0}%</span>
              </article>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.metric}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
```

- [ ] **Step 2: Create route**

Create `src/app/tasks/page.tsx`:

```tsx
import TaskManagerPage from '@/components/tasks/TaskManagerPage';

export default function TasksPage() {
  return <TaskManagerPage />;
}
```

- [ ] **Step 3: Create task CSS**

Create `src/components/tasks/TaskManagerPage.module.css` based on the approved `product-task-manager-v2.html` list-and-modal structure. Required classes:

```css
.page { display: grid; gap: 18px; }
.top { display: flex; justify-content: space-between; align-items: center; gap: 18px; }
.crumb { color: var(--text-secondary); font-size: 13px; font-weight: 700; margin-bottom: 6px; }
.top h1 { font-size: 26px; line-height: 1.15; }
.search { width: 260px; min-height: 40px; border: 1px solid var(--border); background: var(--surface); border-radius: var(--radius-md); padding: 10px 12px; }
.error { border: 1px solid var(--danger-bg); background: #fff7f7; color: var(--danger); border-radius: var(--radius-md); padding: 10px 12px; }
.board { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); box-shadow: var(--shadow-soft); overflow: hidden; }
.toolbar { padding: 14px 16px; border-bottom: 1px solid var(--border-soft); display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.filters { display: flex; gap: 8px; flex-wrap: wrap; }
.chip { border: 1px solid var(--border); background: var(--surface); border-radius: 999px; padding: 7px 9px; color: var(--text-secondary); font-size: 12px; font-weight: 800; }
.chip.active { background: var(--ink); color: #fff; border-color: var(--ink); }
.tableHead, .row { display: grid; grid-template-columns: 36px minmax(240px, 1.4fr) 120px 150px 180px 80px; gap: 10px; align-items: center; padding: 0 16px; }
.tableHead { height: 48px; border-bottom: 1px solid var(--border-soft); background: var(--surface-subtle); color: var(--text-secondary); font-size: 12px; font-weight: 850; }
.row { min-height: 78px; border-bottom: 1px solid var(--border-soft); }
.check { width: 18px; height: 18px; border-radius: 6px; border: 1px solid #cfd8cf; background: #fff; }
.check.checked { background: var(--ink); border-color: var(--ink); }
.title strong, .title span { display: block; }
.title span, .row time { color: var(--text-secondary); font-size: 12px; }
.badge { display: inline-flex; align-items: center; justify-content: center; min-height: 28px; padding: 0 10px; border-radius: 999px; font-size: 12px; font-weight: 900; }
.running, .queued, .searching, .downloading, .rendering, .pending { background: var(--info-bg); color: var(--info); }
.done { background: #e3efd4; color: var(--accent-ink); }
.failed { background: var(--danger-bg); color: var(--danger); }
.progress { display: grid; gap: 6px; color: var(--text-secondary); font-size: 12px; }
.progress i { height: 8px; border-radius: 999px; background: var(--surface-muted); overflow: hidden; }
.progress b { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent-strong), var(--accent)); }
.linkBtn { border: 0; background: transparent; color: var(--accent-ink); font-weight: 850; }
.modalLayer { position: fixed; inset: 0; background: rgba(22, 28, 25, 0.42); display: grid; place-items: center; padding: 24px; z-index: 20; }
.modal { width: min(920px, 100%); max-height: calc(100vh - 48px); overflow: auto; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); box-shadow: 0 30px 70px rgba(15, 20, 18, 0.22); }
.modalHead { position: sticky; top: 0; background: var(--surface); border-bottom: 1px solid var(--border-soft); padding: 16px 18px; display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
.modalHead h2 { font-size: 18px; margin-bottom: 6px; }
.modalHead p { color: var(--text-secondary); font-size: 13px; }
.close { width: 36px; height: 36px; border-radius: var(--radius-md); border: 1px solid var(--border); background: var(--surface); color: var(--ink); font-size: 16px; font-weight: 900; }
.modalBody { padding: 18px; display: grid; gap: 16px; }
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.metric { border: 1px solid var(--border-soft); background: var(--surface-subtle); border-radius: var(--radius-md); padding: 11px; }
.metric span { display: block; color: var(--text-secondary); font-size: 12px; font-weight: 800; margin-bottom: 6px; }
.timeline { display: grid; gap: 10px; }
.event { border: 1px solid var(--border-soft); background: var(--surface); border-radius: var(--radius-md); padding: 12px; display: grid; gap: 8px; }
.event span { color: var(--text-secondary); font-size: 12px; }
@media (max-width: 900px) { .top { align-items: flex-start; flex-direction: column; } .tableHead { display: none; } .row { grid-template-columns: 28px 1fr; align-items: start; padding: 14px 16px; } .row > *:nth-child(n + 3) { grid-column: 2; } .summary { grid-template-columns: repeat(2, 1fr); } }
```

- [ ] **Step 4: Build-check task page**

Run:

```bash
npm run build
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/app/tasks/page.tsx src/components/tasks/TaskManagerPage.tsx src/components/tasks/TaskManagerPage.module.css
git commit -m "feat: add task manager page"
```

---

### Task 8: Final Verification And Browser Review

**Files:**
- Verify only.

- [ ] **Step 1: Run backend tests**

Run:

```bash
python -m unittest tests.test_agent_api_p0 tests.test_agent_persistence tests.test_agent_jobs
```

Expected: pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
npm run build
```

Expected: pass.

- [ ] **Step 3: Start frontend dev server**

Run:

```bash
npm run dev
```

Expected: Next.js starts and prints a localhost URL, usually `http://localhost:3000`.

- [ ] **Step 4: Browser-check required pages**

Open these routes in the in-app browser:

```text
http://localhost:3000/
http://localhost:3000/workspace
http://localhost:3000/tasks
```

Expected:

- Dashboard shows data cards, trend chart, asset mix, and recent tasks.
- Workspace is single-column and does not show the old three-column/side-panel structure.
- User prompt remains raw in the chat bubble.
- AI step blocks show progress tracks before result text.
- Tasks page shows a manageable list.
- Clicking task detail opens a modal, not a persistent side panel.

- [ ] **Step 5: Commit any final visual fixes**

```bash
git add src backend tests
git commit -m "fix: polish product workspace verification issues"
```

Only run this commit if verification found issues and fixes were made.

---

## Self-Review

- Spec coverage: covered dashboard, single-column brief workspace, AI progress-before-result display, raw user prompt, task list management, and modal task detail.
- Tailwind decision: explicitly deferred; this plan keeps CSS Modules for the first productized implementation.
- Backend realism: added minimal read APIs for dashboard and task management instead of inventing frontend-only fake data.
- Placeholder scan: passed; no unresolved placeholder wording remains.
- Type consistency: frontend `AgentTaskSummary`, `AgentTaskDetail`, and `AgentDashboardSummary` match the backend Pydantic response shape.
