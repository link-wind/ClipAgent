# Frontend Creator Canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the ClipForge Agent frontend into the approved Creator Canvas layout while preserving the existing Agent workflow and API behavior.

**Architecture:** Keep the current Next.js client component structure and CSS Modules. Add one small local media helper for shared video URL resolution, render the primary preview from `AgentWorkspace`, and keep detailed progress, plan, chat, and result logic in their existing components.

**Tech Stack:** Next.js 14, React 18, TypeScript, Zustand, CSS Modules, native HTML video controls.

---

## File Structure

- Create `src/components/agent/sessionMedia.ts`
  - Owns local session-derived media helpers.
  - Exports `resolveSessionVideoUrl(session)` so `AgentWorkspace` and `ResultPanel` use the same URL logic.
- Modify `src/app/globals.css`
  - Updates shared CSS variables for the Creator Canvas palette and base page styling.
- Modify `src/components/common/Button.module.css`
  - Updates button styling to match the Creator Canvas palette.
- Modify `src/components/agent/AgentWorkspace.tsx`
  - Keeps restore and polling behavior.
  - Adds the primary result preview region above chat.
  - Uses `resolveSessionVideoUrl`.
- Modify `src/components/agent/AgentWorkspace.module.css`
  - Implements top bar, creator canvas, preview, side rail, and responsive layout.
- Modify `src/components/agent/AgentChat.tsx`
  - Keeps submit and confirm behavior.
  - Adds a small composer hint and adjusts empty-state copy.
- Modify `src/components/agent/AgentChat.module.css`
  - Restyles messages, empty state, composer, and errors.
- Modify `src/components/agent/ProgressPanel.tsx`
  - Adds compact metric values from the current session.
  - Keeps progress, status, current step, workflow steps, and recent events.
- Modify `src/components/agent/ProgressPanel.module.css`
  - Restyles progress and timeline.
- Modify `src/components/agent/PlanPanel.module.css`
  - Restyles plan summary and scene rows.
- Modify `src/components/agent/ResultPanel.tsx`
  - Uses `resolveSessionVideoUrl`.
  - Keeps result detail behavior.
- Modify `src/components/agent/ResultPanel.module.css`
  - Restyles output actions and clip details for the side rail.

---

### Task 1: Add Shared Session Media Helper

**Files:**
- Create: `src/components/agent/sessionMedia.ts`
- Modify: `src/components/agent/ResultPanel.tsx`

- [ ] **Step 1: Create the helper**

Create `src/components/agent/sessionMedia.ts`:

```ts
import type { AgentSession } from '@/lib/agentApi';

export function resolveSessionVideoUrl(session: AgentSession | null | undefined) {
  return (
    session?.videoUrl ||
    session?.clips.find((clip) => clip.publicUrl.includes('/output/'))?.publicUrl ||
    null
  );
}
```

- [ ] **Step 2: Update `ResultPanel` to use the helper**

In `src/components/agent/ResultPanel.tsx`, add this import:

```ts
import { resolveSessionVideoUrl } from './sessionMedia';
```

Replace the existing `videoUrl` assignment:

```ts
const videoUrl =
  session?.videoUrl ||
  session?.clips.find((clip) => clip.publicUrl.includes('/output/'))?.publicUrl ||
  null;
```

with:

```ts
const videoUrl = resolveSessionVideoUrl(session);
```

- [ ] **Step 3: Build-check the helper**

Run:

```bash
npm run build
```

Expected: build passes, or fails only because of pre-existing unrelated environment/backend assumptions. TypeScript must not report missing imports or type errors for `sessionMedia.ts`.

- [ ] **Step 4: Commit**

```bash
git add src/components/agent/sessionMedia.ts src/components/agent/ResultPanel.tsx
git commit -m "refactor: share agent session media helpers"
```

---

### Task 2: Update Global Tokens and Button Styling

**Files:**
- Modify: `src/app/globals.css`
- Modify: `src/components/common/Button.module.css`

- [ ] **Step 1: Replace global color variables**

In `src/app/globals.css`, replace the `:root` block with:

```css
:root {
  --bg-primary: #0f1012;
  --bg-secondary: #141413;
  --bg-surface: #1f201b;
  --bg-elevated: #24231d;
  --accent: #efc75e;
  --accent-contrast: #15110a;
  --accent-alt: #4bbfd0;
  --success: #7fd7a8;
  --danger: #ff8fa0;
  --text-primary: #f4f0e8;
  --text-secondary: #a49c8e;
  --text-muted: #726b61;
  --border: #343229;
  --border-strong: #4c432b;
  --radius-sm: 4px;
  --radius-md: 8px;
}
```

- [ ] **Step 2: Update the global body style**

In `src/app/globals.css`, replace the `body` rule with:

```css
body {
  background:
    linear-gradient(180deg, rgba(239, 199, 94, 0.06), transparent 280px),
    var(--bg-primary);
  color: var(--text-primary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
  overflow: auto;
}
```

- [ ] **Step 3: Update scrollbar colors**

In `src/app/globals.css`, make the scrollbar rules use the new palette:

```css
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

- [ ] **Step 4: Replace button CSS**

Replace `src/components/common/Button.module.css` with:

```css
.btn {
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: inherit;
  font-weight: 800;
  transition: background 150ms ease, border-color 150ms ease, color 150ms ease, opacity 150ms ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 88px;
  white-space: nowrap;
}

.btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.primary {
  background: var(--accent);
  color: var(--accent-contrast);
}

.primary:hover:not(:disabled) {
  background: #f4d37c;
}

.secondary {
  background: var(--bg-elevated);
  color: var(--text-primary);
  border-color: var(--border-strong);
}

.secondary:hover:not(:disabled) {
  border-color: var(--accent);
  background: #2b281f;
}

.danger {
  background: var(--danger);
  color: #1b0b0f;
}

.danger:hover:not(:disabled) {
  background: #ffadba;
}

.sm {
  min-height: 28px;
  padding: 4px 10px;
  font-size: 12px;
}

.md {
  min-height: 38px;
  padding: 8px 16px;
  font-size: 14px;
}

.lg {
  min-height: 44px;
  padding: 12px 24px;
  font-size: 16px;
}
```

- [ ] **Step 5: Build-check styling changes**

Run:

```bash
npm run build
```

Expected: build passes with no CSS module or TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add src/app/globals.css src/components/common/Button.module.css
git commit -m "style: update creator canvas design tokens"
```

---

### Task 3: Build the Creator Canvas Shell and Main Preview

**Files:**
- Modify: `src/components/agent/AgentWorkspace.tsx`
- Modify: `src/components/agent/AgentWorkspace.module.css`

- [ ] **Step 1: Update imports in `AgentWorkspace.tsx`**

Add the helper import:

```ts
import { resolveSessionVideoUrl } from './sessionMedia';
```

- [ ] **Step 2: Add derived preview values**

Inside `AgentWorkspace`, after the store selectors, add:

```ts
const videoUrl = resolveSessionVideoUrl(session);
const sceneCount = session?.plan?.scenes.length ?? 0;
const targetDuration = session?.plan?.targetDuration ?? null;
```

- [ ] **Step 3: Replace the return markup**

Replace the current `return (...)` block in `AgentWorkspace.tsx` with:

```tsx
return (
  <div className={styles.workspace}>
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.brandMark} aria-hidden="true" />
        <div>
          <h1>ClipForge Agent</h1>
          <p>{session?.currentStep || '等待需求'}</p>
        </div>
      </div>
      <span className={styles.statusPill}>{STATUS_LABELS[session?.status || 'idle']}</span>
    </header>

    <main className={styles.main}>
      <section className={styles.canvasColumn} aria-label="Agent 创作画布">
        <section className={styles.previewPanel} aria-label="结果预览">
          <div className={styles.previewFrame}>
            {videoUrl ? (
              <video src={videoUrl} controls preload="metadata" />
            ) : (
              <div className={styles.previewEmpty}>
                <span className={styles.previewBadge}>RESULT PREVIEW</span>
                <h2>{session?.plan?.title || '你的成片会出现在这里'}</h2>
                <p>
                  {session?.plan
                    ? `${session.plan.style} · ${session.plan.targetDuration} 秒 · ${session.plan.scenes.length} 个场景`
                    : '描述主题、风格、时长和素材偏好后，Agent 会先生成剪辑计划。'}
                </p>
              </div>
            )}
          </div>

          <div className={styles.previewInfo}>
            <span className={styles.previewEyebrow}>CREATOR CANVAS</span>
            <h2>{session?.plan?.title || '把一个想法锻造成短视频'}</h2>
            <p>
              {session?.currentStep ||
                '从需求、计划、素材到最终视频，ClipForge 会把每一步创作过程呈现在同一个工作台里。'}
            </p>
            <div className={styles.previewStats}>
              <div>
                <strong>{targetDuration ? `${targetDuration}s` : '--'}</strong>
                <span>目标时长</span>
              </div>
              <div>
                <strong>{sceneCount || '--'}</strong>
                <span>场景</span>
              </div>
              <div>
                <strong>{session?.progress ?? 0}%</strong>
                <span>进度</span>
              </div>
            </div>
          </div>
        </section>

        <section className={styles.chatColumn} aria-label="Agent 对话">
          <AgentChat />
        </section>
      </section>

      <aside className={styles.panelColumn} aria-label="Agent 工作状态">
        <ProgressPanel />
        <PlanPanel />
        <ResultPanel />
      </aside>
    </main>
  </div>
);
```

- [ ] **Step 4: Replace `AgentWorkspace.module.css`**

Replace the file with:

```css
.workspace {
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(239, 199, 94, 0.06), transparent 280px),
    var(--bg-primary);
  color: var(--text-primary);
  display: grid;
  grid-template-rows: 72px minmax(0, 1fr);
}

.header {
  min-height: 72px;
  padding: 0 28px;
  border-bottom: 1px solid rgba(76, 67, 43, 0.72);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  background: rgba(20, 20, 19, 0.92);
}

.brand {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}

.brandMark {
  flex: 0 0 auto;
  width: 34px;
  height: 34px;
  border: 1px solid rgba(239, 199, 94, 0.55);
  border-radius: 8px;
  background: linear-gradient(135deg, rgba(239, 199, 94, 0.95), rgba(75, 191, 208, 0.9));
  box-shadow: 0 0 0 4px rgba(239, 199, 94, 0.08);
}

.header h1 {
  font-size: 18px;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: 0;
}

.header p {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.statusPill {
  flex: 0 0 auto;
  min-width: 82px;
  min-height: 32px;
  padding: 6px 12px;
  border: 1px solid rgba(127, 215, 168, 0.38);
  border-radius: 999px;
  color: #b6f0d0;
  background: rgba(30, 64, 47, 0.45);
  text-align: center;
  font-size: 12px;
  font-weight: 800;
}

.main {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 440px);
  gap: 18px;
  padding: 18px;
}

.canvasColumn,
.panelColumn {
  min-width: 0;
  min-height: 0;
  border: 1px solid rgba(76, 67, 43, 0.72);
  border-radius: 8px;
  background: rgba(23, 24, 25, 0.88);
  box-shadow: 0 20px 70px rgba(0, 0, 0, 0.36);
  overflow: hidden;
}

.canvasColumn {
  display: grid;
  grid-template-rows: minmax(260px, 42vh) minmax(0, 1fr);
}

.previewPanel {
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(220px, 0.42fr) minmax(0, 1fr);
  gap: 20px;
  padding: 22px;
  border-bottom: 1px solid rgba(76, 67, 43, 0.58);
  background:
    linear-gradient(135deg, rgba(239, 199, 94, 0.08), transparent 46%),
    #141414;
}

.previewFrame {
  min-width: 0;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  border: 1px solid rgba(239, 199, 94, 0.4);
  border-radius: 8px;
  background: #090909;
}

.previewFrame video {
  width: 100%;
  height: 100%;
  max-height: 100%;
  border-radius: 6px;
  background: #050505;
  object-fit: contain;
}

.previewEmpty {
  width: 100%;
  min-height: 190px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px;
  border-radius: 6px;
  background:
    linear-gradient(180deg, rgba(0, 0, 0, 0.05), rgba(0, 0, 0, 0.74)),
    linear-gradient(135deg, #173d45, #34301f 48%, #131313);
}

.previewBadge,
.previewEyebrow {
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
}

.previewEmpty h2,
.previewInfo h2 {
  font-size: 28px;
  line-height: 1.12;
  letter-spacing: 0;
}

.previewEmpty p,
.previewInfo p {
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.previewInfo {
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 14px;
}

.previewStats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.previewStats div {
  min-height: 68px;
  padding: 10px;
  border: 1px solid rgba(76, 67, 43, 0.62);
  border-radius: 8px;
  background: rgba(36, 35, 29, 0.64);
}

.previewStats strong {
  display: block;
  color: var(--text-primary);
  font-size: 18px;
}

.previewStats span {
  color: var(--text-secondary);
  font-size: 12px;
}

.chatColumn {
  min-width: 0;
  min-height: 0;
}

.panelColumn {
  overflow-y: auto;
  background: rgba(20, 20, 19, 0.92);
}

@media (max-width: 980px) {
  .workspace {
    min-height: 100dvh;
    grid-template-rows: auto 1fr;
  }

  .header {
    padding: 16px;
    align-items: flex-start;
  }

  .main {
    grid-template-columns: 1fr;
    min-height: auto;
    padding: 14px;
  }

  .canvasColumn {
    grid-template-rows: auto minmax(520px, auto);
  }

  .previewPanel {
    grid-template-columns: 1fr;
  }

  .panelColumn {
    overflow: visible;
  }
}

@media (max-width: 620px) {
  .header {
    flex-direction: column;
    gap: 10px;
  }

  .statusPill {
    align-self: flex-start;
  }

  .previewPanel {
    padding: 16px;
  }

  .previewEmpty h2,
  .previewInfo h2 {
    font-size: 23px;
  }

  .previewStats {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 5: Build-check the shell**

Run:

```bash
npm run build
```

Expected: build passes with no TypeScript or CSS module errors.

- [ ] **Step 6: Commit**

```bash
git add src/components/agent/AgentWorkspace.tsx src/components/agent/AgentWorkspace.module.css
git commit -m "feat: add creator canvas workspace shell"
```

---

### Task 4: Refresh Chat and Composer

**Files:**
- Modify: `src/components/agent/AgentChat.tsx`
- Modify: `src/components/agent/AgentChat.module.css`

- [ ] **Step 1: Update empty-state copy**

In `AgentChat.tsx`, replace the empty state content:

```tsx
<div className={styles.empty}>
  <h2>描述你想生成的视频</h2>
  <p>告诉 Agent 主题、风格、时长和素材偏好，它会先生成剪辑计划。</p>
</div>
```

with:

```tsx
<div className={styles.empty}>
  <span>NEW PROJECT</span>
  <h2>描述你想生成的视频</h2>
  <p>告诉 Agent 主题、风格、时长和素材偏好，它会先生成剪辑计划，并把结果预览放到上方画布。</p>
</div>
```

- [ ] **Step 2: Add composer hint**

In `AgentChat.tsx`, inside `<div className={styles.actions}>` before the first `Button`, add:

```tsx
<span className={styles.composerHint}>Enter 发送 · Shift Enter 换行</span>
```

- [ ] **Step 3: Replace chat CSS**

Replace `src/components/agent/AgentChat.module.css` with:

```css
.chat {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: transparent;
}

.messages {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.empty {
  margin: auto;
  max-width: 560px;
  color: var(--text-secondary);
}

.empty span {
  display: inline-flex;
  margin-bottom: 10px;
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
}

.empty h2 {
  color: var(--text-primary);
  font-size: 22px;
  line-height: 1.2;
  margin-bottom: 10px;
  letter-spacing: 0;
}

.empty p {
  font-size: 14px;
}

.message {
  width: min(74%, 680px);
  padding: 13px 15px;
  border: 1px solid rgba(78, 77, 67, 0.9);
  border-radius: 8px;
  background: rgba(30, 31, 30, 0.88);
}

.userMessage {
  align-self: flex-end;
  background: rgba(22, 59, 65, 0.74);
  border-color: rgba(75, 191, 208, 0.36);
}

.agentMessage {
  align-self: flex-start;
}

.messageMeta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 7px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.message p {
  color: var(--text-primary);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.error {
  margin: 0 22px 14px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 143, 160, 0.42);
  border-radius: 6px;
  color: #ffc0ca;
  background: rgba(63, 22, 29, 0.72);
  overflow-wrap: anywhere;
}

.composer {
  padding: 18px 22px 22px;
  border-top: 1px solid rgba(76, 67, 43, 0.58);
  background: rgba(20, 20, 18, 0.94);
}

.composer textarea {
  width: 100%;
  min-height: 92px;
  max-height: 220px;
  resize: vertical;
  padding: 13px 14px;
  border: 1px solid rgba(83, 79, 63, 0.9);
  border-radius: 8px;
  background: #10100f;
  color: var(--text-primary);
  font: inherit;
  outline: none;
}

.composer textarea:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(239, 199, 94, 0.15);
}

.composer textarea::placeholder {
  color: var(--text-muted);
}

.actions {
  margin-top: 12px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.composerHint {
  margin-right: auto;
  color: var(--text-muted);
  font-size: 12px;
}

@media (max-width: 640px) {
  .messages {
    padding: 18px 16px;
  }

  .message {
    width: 100%;
  }

  .composer {
    padding: 16px;
  }

  .actions {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .composerHint {
    grid-column: 1 / -1;
    margin-right: 0;
  }

  .actions button {
    justify-content: center;
  }
}

@media (max-width: 420px) {
  .actions {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: Build-check chat changes**

Run:

```bash
npm run build
```

Expected: build passes with no JSX or CSS module errors.

- [ ] **Step 5: Commit**

```bash
git add src/components/agent/AgentChat.tsx src/components/agent/AgentChat.module.css
git commit -m "style: refresh agent chat composer"
```

---

### Task 5: Refresh Progress, Plan, and Result Panels

**Files:**
- Modify: `src/components/agent/ProgressPanel.tsx`
- Modify: `src/components/agent/ProgressPanel.module.css`
- Modify: `src/components/agent/PlanPanel.module.css`
- Modify: `src/components/agent/ResultPanel.module.css`

- [ ] **Step 1: Add progress metrics markup**

In `ProgressPanel.tsx`, after the heading and before `progressTrack`, add:

```tsx
<div className={styles.metrics}>
  <div>
    <strong>{session?.plan?.targetDuration ? `${session.plan.targetDuration}s` : '--'}</strong>
    <span>目标时长</span>
  </div>
  <div>
    <strong>{session?.plan?.scenes.length ?? '--'}</strong>
    <span>场景</span>
  </div>
  <div>
    <strong>{STEP_LABELS[status]}</strong>
    <span>状态</span>
  </div>
</div>
```

- [ ] **Step 2: Replace `ProgressPanel.module.css`**

Replace the file with:

```css
.panel {
  padding: 20px;
  border-bottom: 1px solid rgba(76, 67, 43, 0.58);
}

.heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}

.heading h2 {
  font-size: 15px;
  letter-spacing: 0;
}

.heading span {
  color: var(--accent);
  font-size: 13px;
  font-weight: 800;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 16px;
}

.metrics div {
  min-height: 68px;
  padding: 10px;
  border: 1px solid rgba(76, 67, 43, 0.62);
  border-radius: 8px;
  background: rgba(36, 35, 29, 0.64);
}

.metrics strong {
  display: block;
  color: var(--text-primary);
  font-size: 16px;
  overflow-wrap: anywhere;
}

.metrics span {
  color: var(--text-secondary);
  font-size: 12px;
}

.progressTrack {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: var(--border);
}

.progressBar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--accent), var(--accent-alt));
  transition: width 180ms ease;
}

.current {
  display: grid;
  gap: 8px;
  margin: 16px 0;
}

.current div {
  display: grid;
  grid-template-columns: 76px minmax(0, 1fr);
  gap: 10px;
}

.current dt {
  color: var(--text-secondary);
}

.current dd {
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.steps {
  list-style: none;
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.steps + .steps {
  margin-top: 16px;
}

.steps li {
  min-height: 24px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-secondary);
  font-size: 12px;
}

.steps span {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #59513b;
  flex: 0 0 auto;
}

.active {
  color: var(--text-primary) !important;
}

.active span {
  background: var(--accent);
  box-shadow: 0 0 0 4px rgba(239, 199, 94, 0.12);
}
```

- [ ] **Step 3: Replace `PlanPanel.module.css`**

Replace the file with:

```css
.panel {
  padding: 20px;
  border-bottom: 1px solid rgba(76, 67, 43, 0.58);
}

.heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}

.heading h2 {
  font-size: 15px;
  letter-spacing: 0;
}

.heading span {
  color: var(--accent);
  font-size: 12px;
  font-weight: 800;
}

.empty {
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.summary {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin-bottom: 18px;
}

.summary div {
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(76, 67, 43, 0.54);
  border-radius: 8px;
  background: rgba(36, 35, 29, 0.52);
}

.summary dt {
  margin-bottom: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.summary dd {
  color: var(--text-primary);
  font-weight: 700;
  overflow-wrap: anywhere;
}

.scenes {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.scene {
  padding: 13px 0;
  border-top: 1px solid rgba(76, 67, 43, 0.44);
}

.sceneHeader {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 7px;
}

.sceneHeader h3 {
  font-size: 14px;
  letter-spacing: 0;
}

.sceneHeader span {
  color: var(--accent-alt);
  font-size: 12px;
  font-weight: 800;
}

.scene p {
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.meta {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-muted);
  font-size: 12px;
}

.meta span {
  overflow-wrap: anywhere;
}
```

- [ ] **Step 4: Replace `ResultPanel.module.css`**

Replace the file with:

```css
.panel {
  padding: 20px;
  border-bottom: 1px solid rgba(76, 67, 43, 0.58);
}

.heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
}

.heading h2 {
  font-size: 15px;
  letter-spacing: 0;
}

.heading span {
  color: var(--success);
  font-size: 12px;
  font-weight: 800;
}

.empty {
  color: var(--text-secondary);
  overflow-wrap: anywhere;
}

.error {
  margin-bottom: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 143, 160, 0.42);
  border-radius: 6px;
  color: #ffc0ca;
  background: rgba(63, 22, 29, 0.72);
  overflow-wrap: anywhere;
}

.result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result video {
  width: 100%;
  aspect-ratio: 9 / 16;
  max-height: 420px;
  border: 1px solid rgba(239, 199, 94, 0.36);
  border-radius: 8px;
  background: #050505;
  object-fit: contain;
}

.actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.actions a {
  min-height: 36px;
  padding: 8px 12px;
  border: 1px solid var(--border-strong);
  border-radius: 6px;
  color: var(--text-primary);
  background: var(--bg-elevated);
  text-decoration: none;
  font-weight: 800;
  text-align: center;
}

.actions a:hover {
  border-color: var(--accent);
}

.clipListSection {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 4px;
}

.clipListHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.clipListHeader h3 {
  font-size: 13px;
  color: var(--text-primary);
}

.clipListHeader span {
  font-size: 12px;
  color: var(--text-secondary);
}

.clipList {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 9px;
  margin: 0;
  padding: 0;
}

.clipItem {
  padding: 10px;
  border: 1px solid rgba(76, 67, 43, 0.58);
  border-radius: 8px;
  background: rgba(31, 32, 27, 0.72);
}

.clipTitleRow {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.clipTitleRow strong {
  font-size: 13px;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.clipTitleRow span {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--accent);
  font-weight: 800;
}

.clipMeta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin: 0;
}

.clipMeta div {
  min-width: 0;
}

.clipMeta dt {
  margin-bottom: 3px;
  font-size: 11px;
  color: var(--text-muted);
}

.clipMeta dd {
  margin: 0;
  font-size: 12px;
  color: var(--text-primary);
  overflow-wrap: anywhere;
}

.sourceLink {
  display: inline-flex;
  margin-top: 8px;
  font-size: 12px;
  color: var(--accent-alt);
  text-decoration: none;
}

.sourceLink:hover {
  color: #8de3ee;
}
```

- [ ] **Step 5: Build-check panel changes**

Run:

```bash
npm run build
```

Expected: build passes with no JSX or CSS module errors.

- [ ] **Step 6: Commit**

```bash
git add src/components/agent/ProgressPanel.tsx src/components/agent/ProgressPanel.module.css src/components/agent/PlanPanel.module.css src/components/agent/ResultPanel.module.css
git commit -m "style: refresh creator canvas side panels"
```

---

### Task 6: Verify Responsive UI and Final Build

**Files:**
- No intentional source edits.
- Temporary local fixtures or store seeds may be used for manual verification, but must not be committed unless intentionally converted into tests.

- [ ] **Step 1: Run production build**

Run:

```bash
npm run build
```

Expected: build passes.

- [ ] **Step 2: Start the local app**

Run:

```bash
npm run dev
```

Expected: Next.js starts and prints a local URL such as `http://localhost:3000`.

- [ ] **Step 3: Check desktop layout**

Open the local URL at about 1440px width.

Expected:

- Top bar shows brand mark, `ClipForge Agent`, current step text, and status pill.
- Main area is two columns.
- Result preview is above the conversation.
- Side rail shows progress, plan, and result sections.
- No text overlaps or clipped buttons.

- [ ] **Step 4: Check tablet/mobile layout**

Resize to about 900px and 390px width.

Expected:

- Layout collapses to one column.
- Preview appears before chat.
- Side rail sections appear below chat.
- Message bubbles fit within the viewport.
- Composer buttons do not overflow.

- [ ] **Step 5: Check default empty state**

With no active session:

Expected:

- Preview empty state says the final video will appear there.
- Chat empty state asks the user to describe a video.
- Progress/plan/result panels still show useful empty states.

- [ ] **Step 6: Inspect git diff**

Run:

```bash
git status --short
git diff -- src/app/globals.css src/components/common/Button.module.css src/components/agent
```

Expected:

- Only intended frontend files are modified.
- No `.superpowers/brainstorm` files are staged.
- No temporary fixtures or store seeds are present.

- [ ] **Step 7: Commit final verification adjustments if any**

If responsive verification required small CSS fixes, commit them:

```bash
git add src/app/globals.css src/components/common/Button.module.css src/components/agent
git commit -m "fix: tune creator canvas responsive layout"
```

If no changes were needed, do not create an empty commit.

---

## Self-Review Notes

- Spec coverage: This plan covers the shared media helper, top project bar, main preview, two-column/one-column layout, chat/composer styling, progress metrics/timeline, plan styling, result detail styling, global palette, build verification, and responsive visual checks.
- No backend changes are included.
- No new dependency is introduced.
- The helper name `resolveSessionVideoUrl` is defined in Task 1 and used consistently in later tasks.
- Temporary visual test data is allowed only for local verification and must not be committed.
