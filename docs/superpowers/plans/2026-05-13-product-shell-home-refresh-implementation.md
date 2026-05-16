# Product Shell And Homepage Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current left-rail shell with a top-navigation shell, introduce shared visual tokens, refresh the homepage to match the new product direction, and lightly adapt the remaining top-level pages so they fit the new shell without layout regressions.

**Architecture:** Move the shared shell to a Tailwind-first React component and reduce shell-specific styling from CSS modules. Keep a thin layer of global CSS variables in `src/app/globals.css` for shared surfaces, borders, shadows, and text tones. Refresh `DashboardPage` to fully adopt the new shell and visual system, then apply only spacing and container-level compatibility updates to `workspace`, `tasks`, and `settings`.

**Tech Stack:** Next.js App Router, React client components, Tailwind CSS, minimal global CSS variables, existing product pages under `src/components/*`.

---

## File Structure

### Primary files

- Modify: `src/components/layout/ProductShell.tsx`
  - Replace the current left rail layout with a desktop top bar and mobile drawer/collapsible navigation.
- Modify: `src/app/globals.css`
  - Introduce the new cool-white surface tokens, border/shadow/radius values, and shell-related defaults.
- Modify: `src/components/dashboard/DashboardPage.tsx`
  - Recompose the hero, summary cards, process band, and workflow section around the new shell and spacing rhythm.

### Compatibility files

- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
  - Adjust outer spacing and top-level section rhythm so the page sits correctly under the new shell.
- Modify: `src/components/tasks/TaskManagerPage.tsx`
  - Adjust top-level spacing and preserve card consistency under the new shell.
- Modify: `src/components/settings/SettingsPage.tsx`
  - Adjust page container/header spacing to match the new shell.

### Likely cleanup

- Delete or stop importing: `src/components/layout/ProductShell.module.css`
  - Only remove it after the new shell is fully implemented and all imports are gone.

---

### Task 1: Rebuild ProductShell As A Top Navigation Shell

**Files:**
- Modify: `src/components/layout/ProductShell.tsx`
- Delete: `src/components/layout/ProductShell.module.css`
- Test: `src/components/layout/ProductShell.tsx`

- [ ] **Step 1: Write the failing contract test for the new shell layout**

Add or update a frontend contract test in `tests/test_agent_backend.py` to assert the new shell shape:

```python
def test_product_shell_uses_top_navigation_layout(self):
    shell_source = (ROOT / "src" / "components" / "layout" / "ProductShell.tsx").read_text(encoding="utf-8")

    self.assertIn("const NAV_ITEMS = [", shell_source)
    self.assertIn("ClipForge", shell_source)
    self.assertIn("系统就绪", shell_source)
    self.assertIn("aria-label=\"主导航\"", shell_source)
    self.assertIn("md:flex", shell_source)
    self.assertIn("移动导航", shell_source)
    self.assertNotIn("ProductShell.module.css", shell_source)
    self.assertNotIn("styles.rail", shell_source)
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_product_shell_uses_top_navigation_layout
```

Expected: `FAIL` because `ProductShell.tsx` still imports `ProductShell.module.css` and renders the old left rail.

- [ ] **Step 3: Replace the shell component with a Tailwind-first implementation**

Rewrite `src/components/layout/ProductShell.tsx` around this structure:

```tsx
'use client';

import type { ReactNode } from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/', label: '总览' },
  { href: '/workspace', label: '方案' },
  { href: '/tasks', label: '任务' },
  { href: '/settings', label: '设置' },
];

function isItemActive(pathname: string, href: string) {
  return href === '/' ? pathname === '/' : pathname === href || pathname.startsWith(`${href}/`);
}

export default function ProductShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <div className="min-h-screen bg-pagebg text-ink">
      <header className="sticky top-0 z-40 border-b border-border/80 bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1440px] items-center gap-4 px-4 py-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex min-w-0 items-center gap-3 no-underline">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-slate-950 text-lg font-black text-white">
              C
            </span>
            <span className="min-w-0">
              <strong className="block truncate text-xl font-semibold tracking-tight text-ink">ClipForge</strong>
              <span className="block truncate text-sm text-secondary">多智能体短视频制作与执行工作台</span>
            </span>
          </Link>

          <nav
            className="mx-auto hidden items-center gap-2 rounded-full border border-border bg-white/90 p-1 shadow-soft md:flex"
            aria-label="主导航"
          >
            {NAV_ITEMS.map((item) => {
              const active = isItemActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={[
                    'inline-flex min-h-11 items-center rounded-full px-5 text-sm font-semibold transition',
                    active
                      ? 'bg-slate-950 text-white shadow-[0_10px_24px_rgba(15,23,42,0.16)]'
                      : 'text-secondary hover:bg-slate-100 hover:text-ink',
                  ].join(' ')}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto hidden items-center gap-3 md:flex">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              系统就绪
            </span>
            <Link
              href="/settings"
              className="inline-flex min-h-11 items-center rounded-full border border-border bg-white px-4 text-sm font-semibold text-ink transition hover:bg-slate-50"
            >
              设置
            </Link>
          </div>

          <button
            type="button"
            className="ml-auto inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-border bg-white text-ink md:hidden"
            aria-label="打开移动导航"
            aria-expanded={mobileNavOpen}
            onClick={() => setMobileNavOpen((current) => !current)}
          >
            {mobileNavOpen ? '×' : '≡'}
          </button>
        </div>

        {mobileNavOpen ? (
          <div className="border-t border-border bg-white px-4 py-4 shadow-soft md:hidden" aria-label="移动导航">
            <nav className="grid gap-2">
              {NAV_ITEMS.map((item) => {
                const active = isItemActive(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={[
                      'inline-flex min-h-11 items-center rounded-2xl px-4 text-sm font-semibold transition',
                      active ? 'bg-slate-950 text-white' : 'bg-slate-50 text-ink hover:bg-slate-100',
                    ].join(' ')}
                    onClick={() => setMobileNavOpen(false)}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        ) : null}
      </header>

      <main className="mx-auto w-full max-w-[1440px] px-4 pb-10 pt-6 sm:px-6 lg:px-8 lg:pt-8">{children}</main>
    </div>
  );
}
```

- [ ] **Step 4: Remove the old shell CSS module**

Delete the obsolete file:

```bash
rm /Users/linkwind/Code/ClipForge_v2/src/components/layout/ProductShell.module.css
```

Expected follow-up: `git status` shows the CSS module removed and `ProductShell.tsx` modified.

- [ ] **Step 5: Run the shell contract test to verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_product_shell_uses_top_navigation_layout
```

Expected: `OK`

- [ ] **Step 6: Commit the shell rewrite**

```bash
git add src/components/layout/ProductShell.tsx src/components/layout/ProductShell.module.css tests/test_agent_backend.py
git commit -m "feat: replace product shell with top navigation"
```

---

### Task 2: Introduce Shared Global Visual Tokens For The New Shell

**Files:**
- Modify: `src/app/globals.css`
- Test: `src/app/globals.css`

- [ ] **Step 1: Write the failing contract test for the new token set**

Add or update a frontend contract test in `tests/test_agent_backend.py`:

```python
def test_globals_css_exposes_shell_refresh_tokens(self):
    css_source = (ROOT / "src" / "app" / "globals.css").read_text(encoding="utf-8")

    self.assertIn("--page-bg: #f5f7fb;", css_source)
    self.assertIn("--surface: #ffffff;", css_source)
    self.assertIn("--ink: #111b33;", css_source)
    self.assertIn("--text-secondary: #64748b;", css_source)
    self.assertIn("--shadow-soft: 0 18px 40px rgba(148, 163, 184, 0.14);", css_source)
    self.assertIn("--radius-lg: 24px;", css_source)
```

- [ ] **Step 2: Run the token contract test to verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_shell_refresh_tokens
```

Expected: `FAIL` because `globals.css` still contains the old warmer palette and missing radius values.

- [ ] **Step 3: Update `globals.css` to the new cool-white visual system**

Replace the old token block in `src/app/globals.css` with a tighter set like:

```css
:root {
  --page-bg: #f5f7fb;
  --surface: #ffffff;
  --surface-subtle: #f8fbff;
  --surface-muted: #eef3fb;
  --ink: #111b33;
  --text-primary: #111b33;
  --text-secondary: #64748b;
  --text-muted: #94a3b8;
  --border: #dbe3f0;
  --border-soft: #e8eef7;
  --accent: #cfe1ff;
  --accent-strong: #274690;
  --accent-ink: #1f3b73;
  --danger: #b42318;
  --danger-bg: #fef3f2;
  --info: #2563eb;
  --info-bg: #dbeafe;
  --success: #16a34a;
  --shadow-soft: 0 18px 40px rgba(148, 163, 184, 0.14);
  --shadow-hero: 0 28px 60px rgba(148, 163, 184, 0.18);
  --radius-sm: 8px;
  --radius-md: 14px;
  --radius-lg: 24px;
  --bg-primary: var(--page-bg);
  --bg-secondary: var(--surface-subtle);
  --bg-surface: var(--surface);
  --bg-elevated: var(--surface-muted);
  --border-strong: #c9d4e5;
}

html,
body {
  background: var(--page-bg);
}

body {
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}
```

- [ ] **Step 4: Run the token contract test to verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_globals_css_exposes_shell_refresh_tokens
```

Expected: `OK`

- [ ] **Step 5: Commit the token update**

```bash
git add src/app/globals.css tests/test_agent_backend.py
git commit -m "style: refresh shared product shell tokens"
```

---

### Task 3: Refresh DashboardPage To Match The New Product Shell

**Files:**
- Modify: `src/components/dashboard/DashboardPage.tsx`
- Test: `src/components/dashboard/DashboardPage.tsx`

- [ ] **Step 1: Write the failing contract test for the refreshed dashboard composition**

Add or update a frontend contract test in `tests/test_agent_backend.py`:

```python
def test_dashboard_page_matches_shell_refresh_layout(self):
    dashboard_source = (ROOT / "src" / "components" / "dashboard" / "DashboardPage.tsx").read_text(
        encoding="utf-8"
    )

    self.assertIn("编排优先演示", dashboard_source)
    self.assertIn("先定义模式，再观察智能体协作", dashboard_source)
    self.assertIn("grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]", dashboard_source)
    self.assertIn("流程", dashboard_source)
    self.assertIn("Default Workflow", dashboard_source)
```

- [ ] **Step 2: Run the dashboard contract test to verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_dashboard_page_matches_shell_refresh_layout
```

Expected: `FAIL` because the current dashboard still uses the earlier metrics-first layout.

- [ ] **Step 3: Recompose the dashboard hero and summary zone**

In `src/components/dashboard/DashboardPage.tsx`, replace the current top hero section with a two-column composition:

```tsx
<section className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(320px,0.9fr)]">
  <article className="rounded-[30px] border border-border bg-[radial-gradient(circle_at_78%_28%,rgba(207,225,255,0.82),rgba(255,255,255,0.98)_56%)] p-8 shadow-[var(--shadow-hero)]">
    <span className="inline-flex items-center rounded-full bg-[#e8f0ff] px-3 py-1 text-xs font-semibold text-[#2952a3]">
      编排优先演示
    </span>
    <h1 className="mt-5 max-w-[10ch] text-4xl font-semibold leading-[1.02] text-ink sm:text-5xl">
      先定义模式，再观察智能体协作。
    </h1>
    <p className="mt-5 max-w-2xl text-base leading-7 text-secondary">
      在一个视图中查看方案、执行、任务和系统状态，让 ClipForge 首页更像产品入口，而不是单纯的数据列表。
    </p>
    <div className="mt-8 flex flex-wrap gap-3">
      <Link href="/workspace" className="inline-flex min-h-12 items-center rounded-full bg-slate-950 px-6 text-sm font-semibold text-white">
        进入方案工作区
      </Link>
      <Link href="/tasks" className="inline-flex min-h-12 items-center rounded-full border border-border bg-white px-6 text-sm font-semibold text-ink">
        查看任务
      </Link>
    </div>
  </article>

  <div className="grid gap-4">
    {summaryCards.map((card) => (
      <article key={card.label} className="rounded-[28px] border border-border bg-white/96 p-5 shadow-soft">
        <div className="flex items-center justify-between gap-3">
          <div className={`grid h-14 w-14 place-items-center rounded-2xl ${card.iconTone}`} />
          <span className="text-2xl text-slate-300">›</span>
        </div>
        <p className="mt-4 text-sm font-semibold text-secondary">{card.label}</p>
        <strong className="mt-1 block text-4xl font-semibold text-ink">{card.value}</strong>
      </article>
    ))}
  </div>
</section>
```

- [ ] **Step 4: Recompose the process band and workflow module**

Still in `DashboardPage.tsx`, replace the current lower sections with a lighter process band and a calmer workflow module:

```tsx
<section className="rounded-[30px] border border-border bg-white/96 p-6 shadow-soft" aria-label="流程">
  <div className="border-b border-border pb-4">
    <h2 className="text-2xl font-semibold text-ink">流程</h2>
    <p className="mt-2 text-sm leading-6 text-secondary">按下面顺序体验最清晰。</p>
  </div>
  <div className="mt-6 grid gap-6 md:grid-cols-3">
    {[
      { step: '01', title: '创建 Agents', description: '定义可复用专家角色。' },
      { step: '02', title: '定义模式', description: '选择协作模式并创建编排方案。' },
      { step: '03', title: '运行 Playground', description: '发送消息并查看图与追踪。' },
    ].map((item) => (
      <article key={item.step} className="grid gap-4">
        <div className="flex items-center gap-4">
          <span className="text-5xl font-semibold tracking-tight text-[#dce4f3]">{item.step}</span>
          <span className="h-px flex-1 bg-border" />
        </div>
        <div>
          <h3 className="text-2xl font-semibold text-ink">{item.title}</h3>
          <p className="mt-2 text-sm leading-6 text-secondary">{item.description}</p>
        </div>
      </article>
    ))}
  </div>
</section>

<section className="rounded-[30px] border border-border bg-white/96 p-6 shadow-soft" aria-label="Default Workflow">
  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
    <div>
      <h2 className="text-2xl font-semibold text-ink">Default Workflow</h2>
      <p className="mt-2 text-sm leading-6 text-secondary">This setup is loaded first in Run.</p>
    </div>
    <Link href="/workspace" className="text-base font-semibold text-secondary underline-offset-4 hover:underline">
      Go to Run
    </Link>
  </div>
  <div className="mt-6 rounded-[24px] border border-border bg-[#fbfcff] p-6">
    <h3 className="text-3xl font-semibold text-ink">工程师 Chat</h3>
    <p className="mt-3 text-sm text-secondary">workflow_workflow_0588eabf</p>
    <div className="mt-6 flex flex-wrap gap-2">
      <span className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-semibold text-secondary">单 AGENT 对话</span>
      <span className="rounded-full bg-[#dce9ff] px-3 py-1.5 text-xs font-semibold text-[#2952a3]">工程师</span>
    </div>
  </div>
</section>
```

- [ ] **Step 5: Run the dashboard contract test to verify it passes**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_dashboard_page_matches_shell_refresh_layout
```

Expected: `OK`

- [ ] **Step 6: Build the app and manually verify the four key routes**

Run:

```bash
npm run build
```

Expected: build succeeds.

Then run a local dev server and open:

```bash
npm run dev -- --hostname 127.0.0.1 --port 3002
```

Manually check:

- `http://127.0.0.1:3002/`
- `http://127.0.0.1:3002/workspace`
- `http://127.0.0.1:3002/tasks`
- `http://127.0.0.1:3002/settings`

Look for:

- desktop top shell renders,
- homepage hero matches the new direction,
- no overlapping nav on mobile width,
- no page pushed under the header incorrectly.

- [ ] **Step 7: Commit the dashboard refresh**

```bash
git add src/components/dashboard/DashboardPage.tsx tests/test_agent_backend.py
git commit -m "feat: refresh dashboard for product shell redesign"
```

---

### Task 4: Apply Minimal Compatibility Updates To Workspace, Tasks, And Settings

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Modify: `src/components/tasks/TaskManagerPage.tsx`
- Modify: `src/components/settings/SettingsPage.tsx`
- Test: `src/components/workspace/BriefWorkspacePage.tsx`
- Test: `src/components/tasks/TaskManagerPage.tsx`
- Test: `src/components/settings/SettingsPage.tsx`

- [ ] **Step 1: Write the failing compatibility contract tests**

Add or update frontend contract tests in `tests/test_agent_backend.py`:

```python
def test_workspace_page_uses_shell_spacing_refresh(self):
    workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
        encoding="utf-8"
    )

    self.assertIn("mx-auto w-full max-w-[1280px]", workspace_source)
    self.assertIn("gap-5", workspace_source)

def test_tasks_page_uses_shell_spacing_refresh(self):
    tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
        encoding="utf-8"
    )

    self.assertIn("mx-auto w-full max-w-[1280px]", tasks_source)
    self.assertIn("rounded-[28px]", tasks_source)

def test_settings_page_uses_shell_spacing_refresh(self):
    settings_source = (ROOT / "src" / "components" / "settings" / "SettingsPage.tsx").read_text(
        encoding="utf-8"
    )

    self.assertIn("mx-auto w-full max-w-[1280px]", settings_source)
    self.assertIn("rounded-[28px]", settings_source)
```

- [ ] **Step 2: Run the three compatibility tests to verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_uses_shell_spacing_refresh \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_page_uses_shell_spacing_refresh \
  tests.test_agent_backend.FrontendClientContractTests.test_settings_page_uses_shell_spacing_refresh
```

Expected: `FAIL`

- [ ] **Step 3: Apply minimal container-level updates to each page**

Make only outer-container and section-radius adjustments:

`src/components/workspace/BriefWorkspacePage.tsx`

```tsx
<ProductShell>
  <div className="mx-auto grid w-full max-w-[1280px] gap-5">
    <header className="rounded-[28px] border border-border bg-white/96 p-5 shadow-soft sm:p-6">
      ...
    </header>
    <main className="grid w-full gap-5 min-[1080px]:grid-cols-[minmax(0,1fr)_360px]" aria-label="方案工作区">
      ...
    </main>
  </div>
</ProductShell>
```

`src/components/tasks/TaskManagerPage.tsx`

```tsx
<ProductShell>
  <div className="mx-auto w-full max-w-[1280px]">
    <div className="grid min-w-0 gap-5 lg:gap-6">
      <section className="rounded-[28px] border border-border bg-white/96 p-5 shadow-soft sm:p-6" aria-label="任务管理页面">
        ...
      </section>
    </div>
  </div>
</ProductShell>
```

`src/components/settings/SettingsPage.tsx`

```tsx
<ProductShell>
  <div className="mx-auto grid w-full max-w-[1280px] gap-5">
    <section className="rounded-[28px] border border-border bg-white/96 p-5 shadow-soft sm:p-6" aria-label="运行设置">
      ...
    </section>
  </div>
</ProductShell>
```

- [ ] **Step 4: Run the compatibility tests to verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_page_uses_shell_spacing_refresh \
  tests.test_agent_backend.FrontendClientContractTests.test_tasks_page_uses_shell_spacing_refresh \
  tests.test_agent_backend.FrontendClientContractTests.test_settings_page_uses_shell_spacing_refresh
```

Expected: `OK`

- [ ] **Step 5: Run the full frontend contract suite and build**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend.FrontendClientContractTests
npm run build
```

Expected:

- frontend contract suite: `OK`
- build: success

- [ ] **Step 6: Commit the compatibility pass**

```bash
git add src/components/workspace/BriefWorkspacePage.tsx src/components/tasks/TaskManagerPage.tsx src/components/settings/SettingsPage.tsx tests/test_agent_backend.py
git commit -m "style: align top-level pages with refreshed shell"
```

---

## Self-Review

### Spec coverage

- Shell replacement: covered in Task 1.
- Shared visual token refresh: covered in Task 2.
- Homepage refresh: covered in Task 3.
- Minimal compatibility updates for `workspace`, `tasks`, and `settings`: covered in Task 4.
- Verification across `/`, `/workspace`, `/tasks`, `/settings`: covered in Task 3 and Task 4 verification steps.

### Placeholder scan

- No `TODO` or `TBD` placeholders remain.
- Each task contains explicit file paths, commands, and target code snippets.
- Verification commands are concrete and repeatable.

### Type consistency

- Navigation labels stay aligned with current routes: `总览`, `方案`, `任务`, `设置`.
- Shell route matching helper is explicitly defined once and reused in `ProductShell.tsx`.
- Compatibility tasks only change page containers and spacing, not internal business logic.
