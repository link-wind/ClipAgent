# Workspace Conversational Step Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `/workspace` step presentation into a split-layout conversational step flow where cards appear sequentially, the top progress bar grows dynamically, and each visible step card also shows its own dynamic progress.

**Architecture:** Keep the existing `/workspace` left-right layout stable and localize the main UI change to `src/components/workspace/AiStepFlow.tsx`. Introduce a small read-model layer inside the step-flow component so existing session fields can drive visibility, card copy, total progress, and per-step progress without changing backend contracts.

**Tech Stack:** Next.js 14, React 18, TypeScript, CSS Modules, Python `unittest` contract tests

---

## File Structure

### Existing files to modify

- `src/components/workspace/AiStepFlow.tsx`
  - Current fixed step list UI that renders all cards immediately
  - Will become the main conversational step flow component
- `src/components/workspace/AiStepFlow.module.css`
  - Current compact status-panel styling
  - Will be updated to support sequential reply cards and per-card progress bars
- `src/components/workspace/BriefWorkspacePage.tsx`
  - Verify how `/workspace` composes step-related sections and whether copy needs small alignment updates
  - Keep changes narrowly scoped; avoid broad layout rewrites unless required
- `tests/test_agent_backend.py`
  - Extend frontend contract coverage for the new conversational step-flow behavior

### No new files unless implementation proves necessary

- Prefer keeping the read-model helpers inside `AiStepFlow.tsx` first
- Only extract helper files if the component becomes too large during implementation

---

### Task 1: Lock Down Conversational Step Flow Contract In Tests

**Files:**
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Write the failing contract tests for the new step-flow copy and structure**

Add a new test block near the existing workspace/frontend contract tests:

```python
    def test_workspace_step_flow_uses_conversational_progress_cards(self):
        step_flow_source = (ROOT / "src" / "components" / "workspace" / "AiStepFlow.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("buildConversationalStepCards", step_flow_source)
        self.assertIn("只展示已经开始或已经完成的步骤", step_flow_source)
        self.assertIn("下一张卡片会在当前步骤完成后出现", step_flow_source)
        self.assertIn("步骤进度", step_flow_source)
        self.assertIn("step.progress", step_flow_source)
        self.assertIn("session?.progress", step_flow_source)
```

And add a CSS-focused source contract:

```python
    def test_workspace_step_flow_css_supports_card_level_progress(self):
        step_flow_css = (ROOT / "src" / "components" / "workspace" / "AiStepFlow.module.css").read_text(
            encoding="utf-8"
        )

        self.assertIn(".stepProgress", step_flow_css)
        self.assertIn(".stepProgressTrack", step_flow_css)
        self.assertIn(".stepProgressBar", step_flow_css)
        self.assertIn(".stepPlaceholder", step_flow_css)
```

- [ ] **Step 2: Run the focused tests to verify they fail for the current implementation**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_step_flow_uses_conversational_progress_cards \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_step_flow_css_supports_card_level_progress
```

Expected:

- FAIL because `AiStepFlow.tsx` does not yet contain conversational read-model helpers or placeholder copy
- FAIL because `AiStepFlow.module.css` does not yet define step-card progress classes

- [ ] **Step 3: Commit the failing test state only if you are executing this plan in a TDD-friendly isolated branch**

```bash
git add tests/test_agent_backend.py
git commit -m "test: cover conversational workspace step flow"
```

If your workflow does not allow committing red tests alone, skip this commit and proceed immediately to Task 2.

---

### Task 2: Rebuild `AiStepFlow.tsx` Around A Conversational Read Model

**Files:**
- Modify: `src/components/workspace/AiStepFlow.tsx`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add local types and helper functions for visible conversational cards**

Replace the current fixed-step assumptions with a richer local model:

```ts
type StepKey = (typeof STEPS)[number]['key'];

type ConversationalStepCard = {
  key: StepKey;
  label: string;
  statusText: string;
  message: string;
  progress: number;
  isComplete: boolean;
  isActive: boolean;
  isFailed: boolean;
  isVisible: boolean;
  isPlaceholder: boolean;
};

function clampProgress(value: number) {
  return Math.max(0, Math.min(100, value));
}

function buildStepMessage(step: (typeof STEPS)[number], index: number, activeStepIndex: number) {
  if (index < activeStepIndex) {
    return `我已经完成${step.label}，${step.summary}`;
  }
  if (index === activeStepIndex) {
    return `我正在处理${step.label}，${step.summary}`;
  }
  return `下一张卡片会在当前步骤完成后出现。`;
}
```

- [ ] **Step 2: Add a helper that determines which cards are visible and how they should render**

Implement a focused helper inside `AiStepFlow.tsx`:

```ts
function buildConversationalStepCards(status: string, progress: number) {
  const activeStepIndex = getStepIndex(status);

  return STEPS.map((step, index) => {
    const isComplete = index < activeStepIndex || status === 'done';
    const isActive = step.key === status;
    const isFailed = status === 'failed' && step.key === 'failed';
    const isVisible = index <= activeStepIndex;
    const isPlaceholder = index === activeStepIndex + 1 && status !== 'done' && status !== 'failed';
    const stepProgress = isComplete ? 100 : isActive ? clampProgress(progress) : 0;

    return {
      key: step.key,
      label: step.label,
      statusText: isComplete ? '已完成' : isActive ? '进行中' : '等待中',
      message: isPlaceholder ? '下一张卡片会在当前步骤完成后出现。' : buildStepMessage(step, index, activeStepIndex),
      progress: stepProgress,
      isComplete,
      isActive,
      isFailed,
      isVisible,
      isPlaceholder,
    };
  }).filter((card) => card.isVisible || card.isPlaceholder);
}
```

- [ ] **Step 3: Update the component render path to use conversational cards**

Refactor the component body around the new helper:

```ts
  const totalProgress = clampProgress(session?.progress ?? 0);
  const currentStep = session?.currentStep || '等待你描述需求';
  const cards = buildConversationalStepCards(status, totalProgress);
```

Update the list rendering so it no longer maps raw `STEPS`, and instead renders `cards` with:

- conversational status labels
- sequential visibility
- placeholder card after the active step
- per-card progress bar

Use structure like:

```tsx
      <ol className={styles.steps}>
        {cards.map((card) => (
          <li
            key={card.key}
            className={[
              styles.step,
              card.isComplete ? styles.stepComplete : '',
              card.isActive ? styles.stepActive : '',
              card.isFailed ? styles.stepFailed : '',
              card.isPlaceholder ? styles.stepPlaceholder : '',
            ].filter(Boolean).join(' ')}
          >
            <div className={styles.stepMark} aria-hidden="true">
              <span />
            </div>
            <div className={styles.stepBody}>
              <div className={styles.stepTitleRow}>
                <h3>{card.label}</h3>
                <span>{card.statusText}</span>
              </div>
              <p>{card.message}</p>
              <div className={styles.stepProgress}>
                <div className={styles.stepProgressMeta}>
                  <span>步骤进度</span>
                  <span>{card.progress}%</span>
                </div>
                <div className={styles.stepProgressTrack}>
                  <div className={styles.stepProgressBar} style={{ width: `${card.progress}%` }} />
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>
```

- [ ] **Step 4: Run the focused tests to verify the new read-model and copy pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_step_flow_uses_conversational_progress_cards
```

Expected:

- PASS

- [ ] **Step 5: Commit the TypeScript read-model refactor**

```bash
git add src/components/workspace/AiStepFlow.tsx tests/test_agent_backend.py
git commit -m "feat: add conversational workspace step cards"
```

---

### Task 3: Upgrade `AiStepFlow.module.css` To Match The New Card Behavior

**Files:**
- Modify: `src/components/workspace/AiStepFlow.module.css`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Add styles for step-level progress and conversational card density**

Extend the CSS module with dedicated step-progress styles:

```css
.stepProgress {
  margin-top: 10px;
  display: grid;
  gap: 6px;
}

.stepProgressMeta {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  color: var(--text-muted);
  font-size: 11px;
}

.stepProgressTrack {
  height: 6px;
  border-radius: 999px;
  background: rgba(30, 30, 27, 0.96);
  overflow: hidden;
}

.stepProgressBar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(75, 191, 208, 0.95), rgba(239, 199, 94, 0.95));
}
```

- [ ] **Step 2: Add placeholder and active-card styling**

Add styles that make the “next card” placeholder visually lighter:

```css
.stepPlaceholder .stepBody {
  opacity: 0.6;
  border-style: dashed;
}

.stepPlaceholder .stepMark span {
  background: rgba(126, 122, 100, 0.7);
}
```

Also slightly strengthen active-card emphasis if needed:

```css
.stepActive .stepBody {
  border-color: rgba(239, 199, 94, 0.5);
  background: rgba(40, 37, 24, 0.92);
  box-shadow: 0 0 0 1px rgba(239, 199, 94, 0.08);
}
```

- [ ] **Step 3: Run the CSS contract test to verify style hooks exist**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_step_flow_css_supports_card_level_progress
```

Expected:

- PASS

- [ ] **Step 4: Commit the CSS module update**

```bash
git add src/components/workspace/AiStepFlow.module.css tests/test_agent_backend.py
git commit -m "style: refine workspace step flow presentation"
```

---

### Task 4: Align `/workspace` Composition And Verify No Conflicting Step UI Remains

**Files:**
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Inspect whether `BriefWorkspacePage.tsx` duplicates the same planning-step narrative**

Look at the existing `workspaceSteps.map(...)` section around the planning display in:

```tsx
{workspaceSteps.map((step, index) => {
```

Decide whether the new `AiStepFlow` already covers that narrative well enough. If the page currently duplicates step storytelling in a way that makes the new right rail redundant, narrow the in-page copy so it becomes:

- plan detail / result detail oriented
- not a second competing status timeline

Keep the change conservative. Do not delete plan details that users still need.

- [ ] **Step 2: Add a contract test only if page-level wording changes are required**

If you change `BriefWorkspacePage.tsx`, add or update a focused source-level test, for example:

```python
    def test_workspace_step_storytelling_is_owned_by_ai_step_flow(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("AiStepFlow", workspace_source)
        self.assertNotIn("先看进度，再看每一步结果", workspace_source)
```

If no page-level change is needed, skip this step.

- [ ] **Step 3: Run any focused test affected by the page-level adjustment**

Run one of:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_step_storytelling_is_owned_by_ai_step_flow
```

or skip if no new test was added.

- [ ] **Step 4: Commit the page-level cleanup only if a real code change was needed**

```bash
git add src/components/workspace/BriefWorkspacePage.tsx tests/test_agent_backend.py
git commit -m "refactor: keep workspace step storytelling in step flow rail"
```

Skip this commit if no page-level change was necessary.

---

### Task 5: Run Full Verification On The Workspace Change

**Files:**
- Modify: none
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Run the full backend/frontend contract test file**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_agent_backend
```

Expected:

- PASS with the existing workspace and task contract coverage intact

- [ ] **Step 2: Run the production build**

Run:

```bash
npm run build
```

Expected:

- PASS
- No TypeScript or Next.js build regression

- [ ] **Step 3: Commit any final verification-driven fixes**

If verification required additional changes:

```bash
git add src/components/workspace/AiStepFlow.tsx \
  src/components/workspace/AiStepFlow.module.css \
  src/components/workspace/BriefWorkspacePage.tsx \
  tests/test_agent_backend.py
git commit -m "fix: finalize workspace conversational step flow"
```

If no extra fixes were needed after the earlier commits, skip this step.

---

## Self-Review

### Spec coverage

- Sequential cards: covered in Task 2
- Dynamic top progress: preserved and normalized in Task 2
- Dynamic per-card progress: covered in Tasks 2 and 3
- Split layout retained: preserved by scoping changes to `AiStepFlow` and only lightly touching `BriefWorkspacePage` if needed
- Agent-reply tone: covered in Task 2 message-building helpers

### Placeholder scan

- No `TODO` / `TBD`
- All test commands and file paths are explicit
- Optional page-level cleanup is explicitly bounded rather than hand-waved

### Type consistency

- Uses `ConversationalStepCard`, `buildConversationalStepCards`, `clampProgress`, and CSS names consistently across tasks

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-13-workspace-conversational-step-flow.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
