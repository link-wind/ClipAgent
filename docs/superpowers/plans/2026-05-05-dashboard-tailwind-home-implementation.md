# Dashboard Tailwind Home Implementation Plan

> **Status:** Implemented. Recent commits added Tailwind infrastructure, dashboard homepage copy checks, a Tailwind-based Dashboard page, review fixes, and removal of the legacy Dashboard CSS Module. Keep this document as implementation history rather than the next active plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce Tailwind CSS into the Next.js app and rebuild the Dashboard homepage into a product-first ClipForge home without changing the existing dashboard API contract or migrating the other pages.

**Architecture:** Keep `ProductShell` and the existing dashboard data fetch flow in place, but replace the Dashboard page's CSS Module-driven UI with Tailwind classes and a product-first information hierarchy. Add Tailwind through PostCSS plus a small token bridge in `tailwind.config.ts`, preserve current CSS variables in `globals.css`, and use the existing build-time HTML check script to lock in the new homepage copy and structure.

**Tech Stack:** Next.js 14, React 18, TypeScript, Tailwind CSS, PostCSS, existing dashboard API, Node build-time page checks.

---

## File Structure

- Create: `postcss.config.js`
  - Wires Tailwind and Autoprefixer into the Next.js build.
- Create: `tailwind.config.ts`
  - Defines the source scan paths and bridges existing CSS variables into Tailwind theme tokens.
- Modify: `package.json`
  - Adds the Tailwind/PostCSS dev dependencies.
- Modify: `package-lock.json`
  - Captures the installed Tailwind/PostCSS dependency tree.
- Modify: `src/app/globals.css`
  - Adds Tailwind directives while preserving the existing app-wide CSS variables and base styles.
- Modify: `src/components/dashboard/DashboardPage.tsx`
  - Replaces the CSS Module implementation with a Tailwind-based product homepage layout.
- Delete: `src/components/dashboard/DashboardPage.module.css`
  - Removes the old page-specific stylesheet once the page no longer imports it.
- Modify: `scripts/check-product-pages.mjs`
  - Adds dashboard homepage assertions for the new ClipForge-first copy and removes acceptance of the old heading.

---

### Task 1: Add Tailwind Build Infrastructure

**Files:**
- Create: `postcss.config.js`
- Create: `tailwind.config.ts`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `src/app/globals.css`
- Test: `npm run build`

- [ ] **Step 1: Install Tailwind build dependencies**

Run:

```bash
npm install -D tailwindcss postcss autoprefixer
```

Expected: npm updates `package.json` and `package-lock.json`, and exits successfully with new dev dependencies installed.

- [ ] **Step 2: Create the PostCSS config**

Create `postcss.config.js` with:

```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

- [ ] **Step 3: Create the Tailwind config**

Create `tailwind.config.ts` with:

```ts
import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        page: 'var(--page-bg)',
        surface: 'var(--surface)',
        subtle: 'var(--surface-subtle)',
        muted: 'var(--surface-muted)',
        ink: 'var(--ink)',
        primary: 'var(--text-primary)',
        secondary: 'var(--text-secondary)',
        mutedtext: 'var(--text-muted)',
        border: 'var(--border)',
        bordersoft: 'var(--border-soft)',
        accent: 'var(--accent)',
        accentstrong: 'var(--accent-strong)',
        accentink: 'var(--accent-ink)',
        danger: 'var(--danger)',
        infoblue: 'var(--info)',
      },
      boxShadow: {
        soft: 'var(--shadow-soft)',
      },
    },
  },
  plugins: [],
}

export default config
```

- [ ] **Step 4: Add Tailwind directives to global CSS without removing the current design tokens**

Replace `src/app/globals.css` with:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

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

  --bg-primary: var(--page-bg);
  --bg-secondary: var(--surface-subtle);
  --bg-surface: var(--surface);
  --bg-elevated: var(--surface-muted);
  --accent-contrast: var(--accent-ink);
  --accent-alt: var(--accent-strong);
  --success: #7fd7a8;
  --border-strong: #c7cdc7;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html {
  background: var(--page-bg);
}

body {
  background: var(--page-bg);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  letter-spacing: 0;
  overflow: auto;
}

a {
  color: inherit;
}

::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

::-webkit-scrollbar-thumb {
  background: var(--border-strong);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}
```

- [ ] **Step 5: Run the build to verify Tailwind is wired correctly before any homepage refactor**

Run:

```bash
npm run build
```

Expected: the Next.js production build completes successfully with Tailwind enabled and no page code changed yet.

- [ ] **Step 6: Commit the infrastructure slice**

Run:

```bash
git add package.json package-lock.json postcss.config.js tailwind.config.ts src/app/globals.css
git commit -m "build: add tailwind infrastructure"
```

Expected: a commit is created that introduces Tailwind without changing Dashboard behavior yet.

---

### Task 2: Lock In The New Dashboard Copy With A Failing Build-Time Check

**Files:**
- Modify: `scripts/check-product-pages.mjs`
- Test: `npm run build`
- Test: `node scripts/check-product-pages.mjs`

- [ ] **Step 1: Add Dashboard homepage assertions for the new product-first copy**

Update `scripts/check-product-pages.mjs` so `main()` begins with the dashboard checks below before the workspace assertions:

```js
  const dashboardHtml = await readText('.next/server/app/page.html');
  assertIncludes(dashboardHtml, 'ClipForge', 'dashboard 页面缺少产品标题');
  assertIncludes(
    dashboardHtml,
    '对话式短视频制作工作台，把创意 brief 推进成可执行方案、任务流程和最终产出。',
    'dashboard 页面缺少产品定位文案',
  );
  assertIncludes(dashboardHtml, '运行概况', 'dashboard 页面缺少运行概况区块');
  assertIncludes(dashboardHtml, '关键指标', 'dashboard 页面缺少关键指标区块');
  assertIncludes(dashboardHtml, '运行证明', 'dashboard 页面缺少运行证明区块');
  assertIncludes(dashboardHtml, '最近工作', 'dashboard 页面缺少最近工作区块');
  assertExcludes(dashboardHtml, 'Dashboard Home', 'dashboard 页面仍保留旧首页标题');
```

- [ ] **Step 2: Rebuild the app so the current homepage HTML is available to the check script**

Run:

```bash
npm run build
```

Expected: the build still succeeds because only the check script changed.

- [ ] **Step 3: Run the structural check and confirm it fails on the current homepage**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: FAIL with `dashboard 页面缺少产品定位文案` or another new dashboard assertion, because the page still renders the old `Dashboard Home` structure.

---

### Task 3: Rebuild DashboardPage With Tailwind And Product-First Information Hierarchy

**Files:**
- Modify: `src/components/dashboard/DashboardPage.tsx`
- Test: `npm run build`

- [ ] **Step 1: Replace the existing Dashboard page with a Tailwind implementation**

Replace `src/components/dashboard/DashboardPage.tsx` with:

```tsx
'use client';

import { useEffect, useMemo, useState, type CSSProperties } from 'react';
import Link from 'next/link';
import ProductShell from '@/components/layout/ProductShell';
import { getAgentDashboard, type AgentDashboardSummary } from '@/lib/taskApi';

const FALLBACK_DASHBOARD: AgentDashboardSummary = {
  totalSessions: 0,
  activeTasks: 0,
  completedTasks: 0,
  failedTasks: 0,
  recentTasks: [],
};

const TREND_VALUES = [42, 58, 36, 74, 51, 82, 68];

const STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  planning: '规划中',
  plan_ready: '待确认',
  searching: '搜索中',
  downloading: '下载中',
  rendering: '渲染中',
  done: '已完成',
  failed: '失败',
  idle: '待处理',
};

const ASSET_BREAKDOWN = [
  { label: '镜头', value: 38, tone: '#7da577' },
  { label: '素材', value: 27, tone: '#6da7a2' },
  { label: '字幕', value: 18, tone: '#7f93b2' },
  { label: '封面', value: 17, tone: '#c39176' },
];

function formatCount(value: number) {
  return new Intl.NumberFormat('zh-CN').format(value);
}

function formatTaskTime(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value));
}

function getStatusLabel(status: string) {
  return STATUS_LABELS[status] ?? status;
}

function getStatusClasses(status: string) {
  switch (status) {
    case 'done':
      return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
    case 'failed':
      return 'bg-rose-50 text-rose-700 ring-rose-200';
    default:
      return 'bg-sky-50 text-sky-700 ring-sky-200';
  }
}

function getTaskSearchText(task: AgentDashboardSummary['recentTasks'][number]) {
  return `${task.title} ${task.status} ${task.currentStep} ${task.sessionId}`.toLowerCase();
}

function buildDonutBackground() {
  return `conic-gradient(${ASSET_BREAKDOWN.map((item, index) => {
    const start = ASSET_BREAKDOWN.slice(0, index).reduce((sum, next) => sum + next.value, 0);
    const end = start + item.value;
    return `${item.tone} ${start}% ${end}%`;
  }).join(', ')})`;
}

function MetricCard({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint: string;
  accent: string;
}) {
  return (
    <article
      className="rounded-lg border border-border bg-white/95 p-5 shadow-soft"
      style={{ borderTopWidth: '3px', borderTopColor: accent }}
    >
      <span className="block text-sm font-semibold text-secondary">{label}</span>
      <strong className="mt-3 block text-3xl font-semibold leading-none" style={{ color: accent }}>
        {value}
      </strong>
      <span className="mt-3 block text-sm leading-6 text-secondary">{hint}</span>
    </article>
  );
}

function OverviewRow({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-white/90 p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium text-secondary">{label}</span>
        <strong className="text-lg font-semibold text-ink">{value}</strong>
      </div>
      <p className="mt-1 text-xs leading-5 text-mutedtext">{hint}</p>
    </div>
  );
}

function LegendItem({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="grid grid-cols-[12px_minmax(0,1fr)_auto] items-center gap-3">
      <span className="h-3 w-3 rounded-[3px]" style={{ background: tone }} aria-hidden="true" />
      <span className="text-sm text-ink">{label}</span>
      <strong className="text-xs font-semibold text-secondary">{value}%</strong>
    </div>
  );
}

export default function DashboardPage() {
  const [dashboard, setDashboard] = useState<AgentDashboardSummary>(FALLBACK_DASHBOARD);
  const [query, setQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isActive = true;

    const loadDashboard = async () => {
      try {
        setIsLoading(true);
        const nextDashboard = await getAgentDashboard();
        if (isActive) {
          setDashboard(nextDashboard);
          setError(null);
        }
      } catch {
        if (isActive) {
          setDashboard(FALLBACK_DASHBOARD);
          setError('首页数据暂时不可用，已展示本地占位状态。');
        }
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    void loadDashboard();

    return () => {
      isActive = false;
    };
  }, []);

  const metrics = useMemo(
    () => [
      {
        label: '总会话',
        value: formatCount(dashboard.totalSessions),
        hint: '累计接入的方案会话总数',
        accent: '#355e3b',
      },
      {
        label: '活跃任务',
        value: formatCount(dashboard.activeTasks),
        hint: '仍在排队、规划或执行中的任务',
        accent: '#3e6f79',
      },
      {
        label: '已完成',
        value: formatCount(dashboard.completedTasks),
        hint: '已经产出结果、可继续回看的任务',
        accent: '#537b4f',
      },
      {
        label: '失败任务',
        value: formatCount(dashboard.failedTasks),
        hint: '需要重新确认输入或再次发起的任务',
        accent: '#b15a44',
      },
    ],
    [dashboard.activeTasks, dashboard.completedTasks, dashboard.failedTasks, dashboard.totalSessions],
  );

  const filteredTasks = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) {
      return dashboard.recentTasks;
    }
    return dashboard.recentTasks.filter((task) => getTaskSearchText(task).includes(keyword));
  }, [dashboard.recentTasks, query]);

  const activeTrend = useMemo(() => {
    const maxValue = Math.max(...TREND_VALUES);
    return TREND_VALUES.map((value) => ({
      value,
      height: Math.max(18, Math.round((value / maxValue) * 100)),
    }));
  }, []);

  const assetTotal = useMemo(
    () => ASSET_BREAKDOWN.reduce((sum, item) => sum + item.value, 0),
    [],
  );

  const donutStyle = useMemo(
    () =>
      ({
        background: buildDonutBackground(),
      }) as CSSProperties,
    [],
  );

  const hasTasks = filteredTasks.length > 0;

  return (
    <ProductShell>
      <div className="grid min-w-0 gap-4 lg:gap-5">
        <section className="rounded-lg border border-border bg-white/85 p-5 shadow-soft sm:p-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0 max-w-2xl space-y-4">
              <nav className="flex items-center gap-2 text-xs font-medium text-secondary" aria-label="面包屑">
                <Link href="/" className="font-semibold text-ink">
                  总览
                </Link>
                <span aria-hidden="true">/</span>
                <span>ClipForge Home</span>
              </nav>

              <div className="space-y-3">
                <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  Product Home
                </span>
                <h1 className="text-3xl font-semibold tracking-tight text-ink sm:text-4xl">ClipForge</h1>
                <p className="max-w-2xl text-sm leading-6 text-secondary sm:text-base">
                  对话式短视频制作工作台，把创意 brief 推进成可执行方案、任务流程和最终产出。
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <Link
                  href="/workspace"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg bg-ink px-5 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  新建方案
                </Link>
                <Link
                  href="/tasks"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-white px-5 text-sm font-semibold text-ink transition hover:bg-slate-50"
                >
                  任务管理
                </Link>
              </div>
            </div>

            <div className="w-full rounded-lg border border-border bg-slate-50/90 p-4 shadow-soft lg:max-w-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">运行概况</p>
                  <h2 className="mt-1 text-lg font-semibold text-ink">今天的生产状态</h2>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-secondary ring-1 ring-border">
                  {isLoading ? '同步中' : '已同步'}
                </span>
              </div>

              <div className="mt-4 grid gap-3">
                <OverviewRow
                  label="当前会话"
                  value={formatCount(dashboard.totalSessions)}
                  hint="已经进入产品工作台的方案总数"
                />
                <OverviewRow
                  label="正在推进"
                  value={formatCount(dashboard.activeTasks)}
                  hint="此刻还在排队、规划或执行的任务"
                />
                <OverviewRow
                  label="稳定产出"
                  value={formatCount(dashboard.completedTasks)}
                  hint="已经完成、可以回看的最近产出"
                />
              </div>

              <label className="mt-4 block">
                <span className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">
                  搜索任务
                </span>
                <input
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="按标题、状态或会话 ID 筛选"
                  aria-label="搜索任务"
                  className="w-full rounded-lg border border-border bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
                />
              </label>
            </div>
          </div>
        </section>

        {error ? (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 shadow-soft">
            {error}
          </p>
        ) : null}

        <section className="rounded-lg border border-border bg-white/80 p-5 shadow-soft sm:p-6" aria-label="关键指标">
          <div className="flex flex-col gap-2 border-b border-border/80 pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">关键指标</p>
              <h2 className="mt-1 text-xl font-semibold text-ink">正在推进的整体规模</h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-secondary">
              保留现有 dashboard 数据契约，用更产品化的方式表达系统状态。
            </p>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <MetricCard key={metric.label} {...metric} />
            ))}
          </div>
        </section>

        <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.95fr)]" aria-label="运行证明">
          <article className="rounded-lg border border-border bg-white/80 p-5 shadow-soft sm:p-6">
            <div className="flex items-start justify-between gap-3 border-b border-border/80 pb-4">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">运行证明</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">最近 7 个任务产出走势</h2>
              </div>
              <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-secondary">
                {isLoading ? '加载中' : '持续更新'}
              </span>
            </div>

            <div className="mt-6 grid min-h-56 grid-cols-7 items-end gap-3" role="img" aria-label="最近七天生产趋势柱状图">
              {activeTrend.map((item, index) => (
                <div key={`${item.value}-${index}`} className="grid justify-items-center gap-3">
                  <span className="text-xs font-semibold text-secondary">{item.value}</span>
                  <div className="flex h-44 w-full items-end justify-center rounded-t-lg rounded-b bg-slate-100">
                    <span
                      className="block w-6 rounded-t-lg rounded-b bg-gradient-to-b from-slate-700 via-slate-600 to-emerald-500"
                      style={{ height: `${item.height}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>

            <p className="mt-4 text-sm leading-6 text-secondary">
              这组趋势不是监控告警，而是首页上对“最近确实有产出发生”的直接证明。
            </p>
          </article>

          <div className="grid gap-4">
            <article className="rounded-lg border border-border bg-white/80 p-5 shadow-soft">
              <div className="border-b border-border/80 pb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">健康快照</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">当前运行状态</h2>
              </div>

              <div className="mt-4 grid gap-3">
                <OverviewRow
                  label="活跃任务"
                  value={formatCount(dashboard.activeTasks)}
                  hint="还在排队、规划或执行中的任务数量"
                />
                <OverviewRow
                  label="已完成"
                  value={formatCount(dashboard.completedTasks)}
                  hint="已经顺利产出结果的任务数量"
                />
                <OverviewRow
                  label="失败任务"
                  value={formatCount(dashboard.failedTasks)}
                  hint="需要补充输入或重新发起的任务数量"
                />
              </div>
            </article>

            <article className="rounded-lg border border-border bg-white/80 p-5 shadow-soft">
              <div className="border-b border-border/80 pb-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">资源构成</p>
                <h2 className="mt-1 text-xl font-semibold text-ink">当前生产中的资源比例</h2>
              </div>

              <div className="mt-6 grid place-items-center">
                <div className="relative grid place-items-center">
                  <div className="h-44 w-44 rounded-full" style={donutStyle} aria-hidden="true" />
                  <div className="absolute grid h-24 w-24 place-items-center rounded-full bg-white shadow-soft">
                    <strong className="text-3xl font-semibold leading-none text-ink">{assetTotal}%</strong>
                    <span className="text-xs text-secondary">已分配</span>
                  </div>
                </div>
              </div>

              <div className="mt-5 grid gap-3">
                {ASSET_BREAKDOWN.map((item) => (
                  <LegendItem key={item.label} {...item} />
                ))}
              </div>
            </article>
          </div>
        </section>

        <section className="rounded-lg border border-border bg-white/80 p-5 shadow-soft sm:p-6" aria-label="最近工作">
          <div className="flex flex-col gap-3 border-b border-border/80 pb-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.02em] text-secondary">最近工作</p>
              <h2 className="mt-1 text-xl font-semibold text-ink">最新接入的方案队列</h2>
            </div>
            <Link href="/tasks" className="text-sm font-semibold text-ink underline-offset-4 hover:underline">
              前往任务管理
            </Link>
          </div>

          {hasTasks ? (
            <ul className="mt-4 grid gap-3 lg:grid-cols-2">
              {filteredTasks.map((task) => (
                <li
                  key={task.id}
                  className="rounded-lg border border-border bg-slate-50/90 p-4 transition hover:-translate-y-0.5 hover:shadow-soft"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="truncate text-base font-semibold text-ink">{task.title}</h3>
                      <p className="mt-1 text-sm leading-6 text-secondary">
                        {task.currentStep || '等待下一步推进'}
                      </p>
                    </div>
                    <span
                      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ring-1 ${getStatusClasses(task.status)}`}
                    >
                      {getStatusLabel(task.status)}
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-3 text-xs text-secondary">
                    <span>{task.sessionId}</span>
                    <span>{formatTaskTime(task.updatedAt)}</span>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <div className="mt-4 flex flex-col gap-3 rounded-lg border border-dashed border-border bg-slate-50/90 p-5 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm leading-6 text-secondary">最近还没有工作记录，先从一个新方案开始。</p>
              <Link
                href="/workspace"
                className="inline-flex min-h-11 items-center justify-center rounded-lg bg-ink px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                去方案页
              </Link>
            </div>
          )}
        </section>
      </div>
    </ProductShell>
  );
}
```

- [ ] **Step 2: Run the build and catch any Tailwind or TypeScript regressions immediately**

Run:

```bash
npm run build
```

Expected: the homepage compiles successfully with Tailwind classes and no missing import for `DashboardPage.module.css`.

---

### Task 4: Remove The Legacy Dashboard Stylesheet And Verify The New Homepage Contract

**Files:**
- Delete: `src/components/dashboard/DashboardPage.module.css`
- Modify: `scripts/check-product-pages.mjs`
- Test: `npm run build`
- Test: `node scripts/check-product-pages.mjs`

- [ ] **Step 1: Delete the old dashboard CSS Module**

Run:

```bash
git rm src/components/dashboard/DashboardPage.module.css
```

Expected: the obsolete page stylesheet is removed from the worktree because the page now uses Tailwind classes directly.

- [ ] **Step 2: Rebuild the app after removing the stylesheet**

Run:

```bash
npm run build
```

Expected: the build still passes, proving the dashboard page no longer depends on the deleted CSS Module.

- [ ] **Step 3: Re-run the product page structural checks**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: PASS with `product page checks passed`, confirming the Dashboard homepage now renders the new ClipForge-first copy and the existing workspace/tasks checks still hold.

- [ ] **Step 4: Commit the homepage migration**

Run:

```bash
git add package.json package-lock.json postcss.config.js tailwind.config.ts src/app/globals.css src/components/dashboard/DashboardPage.tsx scripts/check-product-pages.mjs
git commit -m "feat: migrate dashboard home to tailwind"
```

Expected: a single feature commit captures the Tailwind setup, homepage refactor, structural checks, and stylesheet cleanup.
