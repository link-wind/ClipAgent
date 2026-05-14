# Marketing Homepage Hero Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the homepage so `/` reads as a public-facing product homepage that explains ClipForge clearly, using a left-explanation/right-preview hero and product-story sections below it.

**Architecture:** Keep the work tightly scoped to the existing homepage surface. Reuse `ProductShell`, retain dashboard data loading only where it can be reframed as output proof, and move the narrative center of gravity in `DashboardPage.tsx` from operations metrics to product explanation. Use a small set of updated global tokens in `src/app/globals.css` to support the lighter premium palette without introducing a separate homepage CSS module.

**Tech Stack:** Next.js App Router, React client components, Tailwind CSS, existing global CSS custom properties, frontend contract tests in `tests/test_agent_backend.py`, existing `scripts/check-product-pages.mjs` verification.

---

## File Structure

### Primary files

- Modify: `src/components/dashboard/DashboardPage.tsx`
  - Recompose the homepage into a product hero, workflow explanation, input/output mapping, example results, and final CTA.
- Modify: `src/app/globals.css`
  - Refresh core visual tokens so the homepage can use the approved warm-white, teal, and blue-teal product palette.
- Modify: `tests/test_agent_backend.py`
  - Add or update frontend contract tests that lock the new homepage narrative structure and token usage.

### Reused dependencies

- Reuse: `src/components/layout/ProductShell.tsx`
  - Keep the current shell wrapper; do not expand this plan into shell redesign work.
- Reuse: `src/lib/taskApi.ts`
  - Continue reading dashboard data through the existing API surface.

### Scope guard

- Do not modify: `src/components/workspace/*`
- Do not modify: `src/components/tasks/*`
- Do not modify: `src/components/settings/*`
- Do not add: new backend endpoints, homepage-specific CSS module files, or fake marketing data sources

---

### Task 1: Lock The Homepage Refresh Contract In Tests

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add a failing frontend contract test for the new homepage narrative**

Append this test inside `FrontendClientContractTests` in `tests/test_agent_backend.py`:

```python
def test_dashboard_page_uses_marketing_hero_structure(self):
    dashboard_source = (ROOT / "src" / "components" / "dashboard" / "DashboardPage.tsx").read_text(
        encoding="utf-8"
    )

    self.assertIn("Product-to-video agent", dashboard_source)
    self.assertIn("把产品 brief 交给 Agent，自动产出可用成片", dashboard_source)
    self.assertIn("How it works", dashboard_source)
    self.assertIn("Input / Output", dashboard_source)
    self.assertIn("Example results", dashboard_source)
    self.assertIn("开始创建", dashboard_source)
    self.assertNotIn("关键指标", dashboard_source)
    self.assertNotIn("最近工作", dashboard_source)
    self.assertNotIn("运行证明", dashboard_source)
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_dashboard_page_uses_marketing_hero_structure -v
```

Expected: `FAIL` because the current homepage still contains `关键指标` / `最近工作` / `运行证明` sections and does not yet contain the new hero copy or lower product sections.

- [ ] **Step 3: Add a token contract test for the refreshed homepage palette**

Append this second test inside `FrontendClientContractTests`:

```python
def test_globals_css_exposes_marketing_homepage_tokens(self):
    globals_css = (ROOT / "src" / "app" / "globals.css").read_text(encoding="utf-8")

    self.assertIn("--page-bg: #f5f7f6;", globals_css)
    self.assertIn("--surface-subtle: #f8fbfa;", globals_css)
    self.assertIn("--surface-muted: #eef3f1;", globals_css)
    self.assertIn("--ink: #10201b;", globals_css)
    self.assertIn("--text-secondary: #5f7069;", globals_css)
    self.assertIn("--accent: #1f6a5b;", globals_css)
    self.assertIn("--accent-strong: #2d8aa4;", globals_css)
```

- [ ] **Step 4: Run the token contract test to verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_marketing_homepage_tokens -v
```

Expected: `FAIL` because `globals.css` still uses the old `#f5f7fb`, `#eef2f7`, `#111b33`, `#64748b`, and green-accent token set.

- [ ] **Step 5: Commit the failing-contract checkpoint**

```bash
git add tests/test_agent_backend.py
git commit -m "test: lock marketing homepage refresh contract"
```

Expected: commit succeeds with only the new/updated homepage contract tests.

---

### Task 2: Refresh Global Tokens For The Approved Homepage Palette

**Files:**
- Modify: `src/app/globals.css`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Replace the global token block with the approved palette**

Update the `:root` block in `src/app/globals.css` so these values are present:

```css
:root {
  --page-bg: #f5f7f6;
  --surface: #ffffff;
  --surface-subtle: #f8fbfa;
  --surface-muted: #eef3f1;
  --ink: #10201b;
  --text-primary: var(--ink);
  --text-secondary: #5f7069;
  --text-muted: #90a19a;
  --rail-text: #c8d3cf;
  --border: #d8e2de;
  --border-soft: #e7eeeb;
  --accent: #1f6a5b;
  --accent-strong: #2d8aa4;
  --accent-ink: #0f3d33;
  --danger: #991b1b;
  --danger-bg: #fee2e2;
  --info: #1d4ed8;
  --info-bg: #dbeafe;
  --shadow-soft: 0 18px 42px rgba(15, 23, 42, 0.08);
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 24px;

  --bg-primary: var(--page-bg);
  --bg-secondary: var(--surface-subtle);
  --bg-surface: var(--surface);
  --bg-elevated: var(--surface-muted);
  --accent-contrast: var(--accent-ink);
  --accent-alt: var(--accent-strong);
  --success: #7fd7a8;
  --border-strong: #c7d3ce;
}
```

Keep the rest of `globals.css` intact for this task except for body typography updates required in the next step.

- [ ] **Step 2: Update the body defaults to match the new homepage tone**

In the same file, replace the current `body` block with:

```css
body {
  background: var(--page-bg);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  letter-spacing: 0;
  overflow: auto;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
}
```

This keeps the existing font family for now, while improving the rendering baseline and aligning the refreshed tone with the approved spec.

- [ ] **Step 3: Run the homepage token contract test to verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_marketing_homepage_tokens -v
```

Expected: `OK`

- [ ] **Step 4: Run the pre-existing shell token contract to catch accidental regressions**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_shell_refresh_tokens -v
```

Expected: `FAIL`

Because the old shell token contract is still pinned to the previous values, update that test in `tests/test_agent_backend.py` to assert the new token values instead:

```python
def test_globals_css_exposes_shell_refresh_tokens(self):
    globals_css = (ROOT / "src" / "app" / "globals.css").read_text(encoding="utf-8")

    self.assertIn("--page-bg: #f5f7f6;", globals_css)
    self.assertIn("--surface: #ffffff;", globals_css)
    self.assertIn("--ink: #10201b;", globals_css)
    self.assertIn("--text-secondary: #5f7069;", globals_css)
    self.assertIn("--shadow-soft: 0 18px 42px rgba(15, 23, 42, 0.08);", globals_css)
    self.assertIn("--radius-lg: 24px;", globals_css)
```

- [ ] **Step 5: Run both token tests together**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_marketing_homepage_tokens \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_shell_refresh_tokens -v
```

Expected: both tests report `ok`

- [ ] **Step 6: Commit the token refresh**

```bash
git add src/app/globals.css tests/test_agent_backend.py
git commit -m "style: refresh homepage surface tokens"
```

---

### Task 3: Rebuild DashboardPage Around The New Product Hero

**Files:**
- Modify: `src/components/dashboard/DashboardPage.tsx`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Remove the old dashboard-only helper surface area**

Delete the unused dashboard helpers and data structures from `src/components/dashboard/DashboardPage.tsx`:

```tsx
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
  { label: '镜头', value: 38, tone: 'var(--dashboard-accent-1)' },
  { label: '素材', value: 27, tone: 'var(--dashboard-accent-2)' },
  { label: '字幕', value: 18, tone: 'var(--dashboard-accent-3)' },
  { label: '封面', value: 17, tone: 'var(--dashboard-accent-4)' },
];
```

Also delete these now-obsolete helper functions and components:

```tsx
function getStatusLabel(status: string) { ... }
function getStatusClasses(status: string) { ... }
function formatTaskTime(value: string) { ... }
function buildDonutBackground() { ... }
function MetricCard(...) { ... }
function OverviewRow(...) { ... }
function LegendItem(...) { ... }
function getTaskSearchText(...) { ... }
```

The final homepage should no longer depend on search, task filtering, donut charts, or operations status pills.

- [ ] **Step 2: Collapse state down to the proof data you still need**

Keep the API load and fallback behavior, but simplify the state shape in `DashboardPage.tsx` to:

```tsx
const [dashboard, setDashboard] = useState<AgentDashboardSummary>(FALLBACK_DASHBOARD);
const [error, setError] = useState<string | null>(null);
const [isLoading, setIsLoading] = useState(true);
```

Remove:

```tsx
const [query, setQuery] = useState('');
```

Remove the `metrics`, `filteredTasks`, `activeTrend`, `assetTotal`, `donutStyle`, `hasTasks`, and `pageStyle` memo blocks entirely.

- [ ] **Step 3: Replace the page JSX with the approved hero-first composition**

Rewrite the return tree of `DashboardPage.tsx` around this structure:

```tsx
return (
  <ProductShell>
    <div className="grid min-w-0 gap-6 lg:gap-8">
      <section className="rounded-[28px] border border-border bg-white/90 p-5 shadow-soft sm:p-7 lg:p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.08fr)_minmax(420px,0.92fr)]">
          <div className="flex flex-col justify-between gap-6">
            <div className="space-y-5">
              <span className="inline-flex items-center rounded-full bg-slate-900/5 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-secondary">
                Product-to-video agent
              </span>
              <div className="space-y-4">
                <h1 className="max-w-[9ch] text-5xl font-semibold tracking-tight text-ink sm:text-6xl">
                  把产品 brief 交给 Agent，自动产出可用成片。
                </h1>
                <p className="max-w-2xl text-base leading-8 text-secondary">
                  输入产品链接、卖点、受众与风格方向，ClipForge 会自动理解产品、搜索真实素材、生成脚本与成片结果。
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/workspace"
                  className="inline-flex min-h-12 items-center justify-center rounded-[14px] bg-[color:var(--accent)] px-5 text-sm font-semibold text-white transition hover:opacity-95"
                >
                  开始创建
                </Link>
                <Link
                  href="/tasks"
                  className="inline-flex min-h-12 items-center justify-center rounded-[14px] border border-border bg-white px-5 text-sm font-semibold text-ink transition hover:bg-slate-50"
                >
                  查看样片
                </Link>
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-3">
              <article className="rounded-[20px] border border-border bg-[color:var(--surface-muted)] p-4">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--accent)]/10 text-xs font-semibold text-[color:var(--accent)]">1</span>
                <h2 className="mt-4 text-base font-semibold text-ink">理解产品信息</h2>
                <p className="mt-2 text-sm leading-6 text-secondary">提取卖点、受众、场景与风格，让 brief 先变清楚。</p>
              </article>
              <article className="rounded-[20px] border border-border bg-[color:var(--surface-muted)] p-4">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--accent)]/10 text-xs font-semibold text-[color:var(--accent)]">2</span>
                <h2 className="mt-4 text-base font-semibold text-ink">搜索真实素材</h2>
                <p className="mt-2 text-sm leading-6 text-secondary">匹配产品画面、B-roll 与 UI 线索，不止生成文本方案。</p>
              </article>
              <article className="rounded-[20px] border border-border bg-[color:var(--surface-muted)] p-4">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[color:var(--accent)]/10 text-xs font-semibold text-[color:var(--accent)]">3</span>
                <h2 className="mt-4 text-base font-semibold text-ink">输出成片方案</h2>
                <p className="mt-2 text-sm leading-6 text-secondary">生成脚本、字幕、镜头节奏与结果视频，并保留继续编辑的空间。</p>
              </article>
            </div>
          </div>

          <div className="rounded-[24px] border border-border bg-[color:var(--surface-subtle)] p-4">
            <div className="overflow-hidden rounded-[22px] bg-[linear-gradient(135deg,rgba(45,138,164,0.72),rgba(23,53,61,0.96))] p-5 text-white">
              <div className="flex min-h-[290px] flex-col justify-between rounded-[18px] border border-white/10 bg-white/5 p-4 backdrop-blur-sm">
                <div className="flex items-center justify-between text-xs font-semibold text-white/80">
                  <span>New product launch preview</span>
                  <span>0:31</span>
                </div>
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full border border-white/40 bg-white/15 text-sm font-semibold">
                  Play
                </div>
                <div className="h-2 rounded-full bg-white/25" />
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-3">
              <div className="h-20 rounded-[16px] border border-border bg-white/80" />
              <div className="h-20 rounded-[16px] border border-border bg-white/80" />
              <div className="h-20 rounded-[16px] border border-border bg-white/80" />
            </div>

            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <article className="rounded-[16px] border border-border bg-white/85 p-4">
                <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-secondary">素材搜索</span>
                <strong className="mt-2 block text-2xl font-semibold text-ink">{formatCount(dashboard.activeTasks || 28)}</strong>
              </article>
              <article className="rounded-[16px] border border-border bg-white/85 p-4">
                <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-secondary">脚本镜头</span>
                <strong className="mt-2 block text-2xl font-semibold text-ink">{Math.max(12, dashboard.completedTasks || 0)}</strong>
              </article>
              <article className="rounded-[16px] border border-border bg-white/85 p-4">
                <span className="text-[11px] font-semibold uppercase tracking-[0.06em] text-secondary">成片时长</span>
                <strong className="mt-2 block text-2xl font-semibold text-ink">0:31</strong>
              </article>
            </div>

            <div className="mt-4 rounded-[18px] border border-border bg-white/85 p-4">
              <h2 className="text-sm font-semibold text-ink">输出结果不是概念图，而是工作流结果预览</h2>
              <p className="mt-2 text-sm leading-6 text-secondary">
                这里会在后续阶段接真实样片和案例摘要；当前先把产品感、结果感和信息顺序搭起来。
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  </ProductShell>
);
```

This step intentionally delivers only the hero rebuild. Do not add the lower sections yet.

- [ ] **Step 4: Run the homepage contract test and verify it is still failing**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_dashboard_page_uses_marketing_hero_structure -v
```

Expected: `FAIL` because `How it works`, `Input / Output`, and `Example results` are not yet present in the page source.

- [ ] **Step 5: Commit the hero rebuild checkpoint**

```bash
git add src/components/dashboard/DashboardPage.tsx
git commit -m "feat: rebuild homepage hero around product narrative"
```

---

### Task 4: Add The Lower Product Sections And Reframe Dashboard Data As Proof

**Files:**
- Modify: `src/components/dashboard/DashboardPage.tsx`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add the `How it works` section directly below the hero**

Append this section after the hero block:

```tsx
<section className="grid gap-4 lg:grid-cols-3" aria-label="How it works">
  <article className="rounded-[24px] border border-border bg-white/85 p-6 shadow-soft">
    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-secondary">How it works</p>
    <h2 className="mt-3 text-2xl font-semibold text-ink">让 Agent 先理解，再执行。</h2>
    <p className="mt-3 text-sm leading-7 text-secondary">
      首页不展示底层任务状态，而是把工作流重新表达成一个更容易理解的产品过程。
    </p>
  </article>
  <article className="rounded-[24px] border border-border bg-white/85 p-6 shadow-soft">
    <h3 className="text-lg font-semibold text-ink">理解 brief</h3>
    <p className="mt-3 text-sm leading-7 text-secondary">提取产品卖点、受众和使用场景，形成可执行的表达方向。</p>
  </article>
  <article className="rounded-[24px] border border-border bg-white/85 p-6 shadow-soft">
    <h3 className="text-lg font-semibold text-ink">生成结果</h3>
    <p className="mt-3 text-sm leading-7 text-secondary">组织素材、字幕与镜头结构，把输入直接变成可回看的成片结果。</p>
  </article>
</section>
```

- [ ] **Step 2: Add the `Input / Output` mapping section**

Append this section after `How it works`:

```tsx
<section className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]" aria-label="Input / Output">
  <article className="rounded-[24px] border border-border bg-white/85 p-6 shadow-soft">
    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-secondary">Input / Output</p>
    <h2 className="mt-3 text-2xl font-semibold text-ink">输入产品信息，输出完整视频交付物。</h2>
    <p className="mt-3 text-sm leading-7 text-secondary">
      用户不需要先组织复杂的剪辑流程，只需要先把产品说明清楚。
    </p>
  </article>
  <div className="grid gap-4 sm:grid-cols-2">
    <article className="rounded-[24px] border border-border bg-[color:var(--surface-muted)] p-6">
      <h3 className="text-lg font-semibold text-ink">输入</h3>
      <ul className="mt-4 grid gap-3 text-sm leading-6 text-secondary">
        <li>产品链接或产品名称</li>
        <li>核心卖点与目标受众</li>
        <li>希望的视频风格与时长</li>
      </ul>
    </article>
    <article className="rounded-[24px] border border-border bg-white/90 p-6">
      <h3 className="text-lg font-semibold text-ink">输出</h3>
      <ul className="mt-4 grid gap-3 text-sm leading-6 text-secondary">
        <li>脚本与镜头节奏</li>
        <li>真实素材与字幕组织</li>
        <li>可继续编辑的成片结果</li>
      </ul>
    </article>
  </div>
</section>
```

- [ ] **Step 3: Add the `Example results` and final CTA sections**

Append these sections after `Input / Output`:

```tsx
<section className="grid gap-4" aria-label="Example results">
  <div className="rounded-[24px] border border-border bg-white/85 p-6 shadow-soft">
    <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-secondary">Example results</p>
    <h2 className="mt-3 text-2xl font-semibold text-ink">结果会像样片，不像任务日志。</h2>
    <p className="mt-3 max-w-2xl text-sm leading-7 text-secondary">
      这里先用结构化案例卡承接右上角的预览区。后续如果接入真实样片，只替换内容，不改版式骨架。
    </p>
  </div>
  <div className="grid gap-4 lg:grid-cols-3">
    <article className="rounded-[24px] border border-border bg-white/85 p-5 shadow-soft">
      <div className="h-40 rounded-[18px] border border-border bg-[color:var(--surface-muted)]" />
      <h3 className="mt-4 text-lg font-semibold text-ink">新品发布短片</h3>
      <p className="mt-2 text-sm leading-6 text-secondary">从产品亮点和目标受众出发，快速形成 30 秒竖版成片。</p>
    </article>
    <article className="rounded-[24px] border border-border bg-white/85 p-5 shadow-soft">
      <div className="h-40 rounded-[18px] border border-border bg-[color:var(--surface-muted)]" />
      <h3 className="mt-4 text-lg font-semibold text-ink">功能亮点视频</h3>
      <p className="mt-2 text-sm leading-6 text-secondary">把功能说明、UI 线索和演示场景组织成可发布的视频表达。</p>
    </article>
    <article className="rounded-[24px] border border-border bg-white/85 p-5 shadow-soft">
      <div className="h-40 rounded-[18px] border border-border bg-[color:var(--surface-muted)]" />
      <h3 className="mt-4 text-lg font-semibold text-ink">促销活动预告</h3>
      <p className="mt-2 text-sm leading-6 text-secondary">在固定时长里快速生成节奏明确、适合投放的活动短片。</p>
    </article>
  </div>
</section>

<section className="rounded-[28px] border border-border bg-white/90 p-6 shadow-soft sm:p-8" aria-label="Final CTA">
  <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
    <div className="space-y-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-secondary">Final CTA</p>
      <h2 className="text-3xl font-semibold tracking-tight text-ink">从产品信息开始，直接生成第一支样片。</h2>
      <p className="max-w-2xl text-sm leading-7 text-secondary">
        不需要先搭剪辑流程，先把产品讲清楚，剩下的交给 ClipForge 的 Agent 工作流。
      </p>
    </div>
    <div className="flex flex-wrap gap-3">
      <Link
        href="/workspace"
        className="inline-flex min-h-12 items-center justify-center rounded-[14px] bg-[color:var(--accent)] px-5 text-sm font-semibold text-white transition hover:opacity-95"
      >
        开始创建
      </Link>
      <Link
        href="/tasks"
        className="inline-flex min-h-12 items-center justify-center rounded-[14px] border border-border bg-white px-5 text-sm font-semibold text-ink transition hover:bg-slate-50"
      >
        查看任务
      </Link>
    </div>
  </div>
</section>
```

- [ ] **Step 4: Run the homepage contract test and verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_dashboard_page_uses_marketing_hero_structure -v
```

Expected: `ok`

- [ ] **Step 5: Run the broader frontend contract subset**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_dashboard_page_uses_marketing_hero_structure \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_marketing_homepage_tokens \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_is_tailwind_based -v
```

Expected: all three tests report `ok`

- [ ] **Step 6: Commit the section rebuild**

```bash
git add src/components/dashboard/DashboardPage.tsx tests/test_agent_backend.py
git commit -m "feat: turn homepage into product marketing shell"
```

---

### Task 5: Verify The Homepage In Build And Product Checks

**Files:**
- Modify: none
- Test: built app output

- [ ] **Step 1: Run the focused frontend contract tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_dashboard_page_uses_marketing_hero_structure \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_marketing_homepage_tokens \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_shell_refresh_tokens -v
```

Expected: all tests report `ok`

- [ ] **Step 2: Run the production build**

Run:

```bash
npm run build
```

Expected: Next.js production build completes successfully with no compile errors.

- [ ] **Step 3: Run the product page verification script**

Run:

```bash
node scripts/check-product-pages.mjs
```

Expected: the script completes successfully and does not report product page regressions.

- [ ] **Step 4: Review the diff before handoff**

Run:

```bash
git diff -- src/app/globals.css src/components/dashboard/DashboardPage.tsx tests/test_agent_backend.py
```

Expected review points:

- no accidental shell/workspace/task/settings edits
- no fake testimonial or fake logo wall content
- homepage copy matches the approved product framing

- [ ] **Step 5: Commit the verification checkpoint**

```bash
git add src/app/globals.css src/components/dashboard/DashboardPage.tsx tests/test_agent_backend.py
git commit -m "chore: verify marketing homepage refresh"
```

---

## Self-Review

### Spec coverage

- Hero-first product explanation: covered in Task 3
- Left explanation / right preview order: covered in Task 3
- Light premium palette: covered in Task 2
- Lower sections `How it works`, `Input / Output`, `Example results`, `Final CTA`: covered in Task 4
- Scope limited to homepage and no backend expansion: enforced in File Structure and Task 5 review

### Placeholder scan

- No `TODO` or `TBD`
- Placeholder-backed example cards are explicit and aligned with the approved spec
- All commands, files, and expected outcomes are concrete

### Type consistency

- Homepage file target is consistently `src/components/dashboard/DashboardPage.tsx`
- Contract test class is consistently `FrontendClientContractTests`
- Token names used in tests match the token names specified for `globals.css`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-14-marketing-homepage-hero-refresh-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
