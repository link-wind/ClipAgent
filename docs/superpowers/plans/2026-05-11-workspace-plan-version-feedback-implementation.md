# Workspace Plan Version Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `currentPlanVersion` through the agent session contract and use it in `/workspace` to show a reliable “plan updated” notice after user revision replans.

**Architecture:** The backend will switch session reads from “latest plan by session” semantics to “current plan pointed by `current_plan_id`” semantics, then surface that version as `currentPlanVersion` on `AgentSession`. The frontend will keep its existing `sendAgentMessage(...) -> setSession(nextSession)` flow, but compare the returned version with the pre-submit version and render an inline success notice only when the version truly increments.

**Tech Stack:** Python `unittest`, FastAPI/Pydantic backend models, SQLAlchemy repositories, Next.js/React client, Zustand store, Tailwind-based workspace UI

---

## File Structure

- `backend/models/agent.py`
  - Extend the backend `AgentSession` response model with `currentPlanVersion`.
- `backend/services/agent_read_service.py`
  - Load the current plan row from `session_record.current_plan_id` and populate both `plan` and `currentPlanVersion` from that same row.
- `tests/test_agent_persistence.py`
  - Add backend regression coverage for initial plan version exposure, revision version increment, and “current pointer beats latest plan” semantics.
- `src/lib/agentApi.ts`
  - Extend the frontend `AgentSession` TypeScript contract with `currentPlanVersion`.
- `src/components/workspace/BriefWorkspacePage.tsx`
  - Track whether a successful revision produced a higher plan version and show the inline “已根据你的修改更新计划” notice near the final plan block.
- `tests/test_agent_backend.py`
  - Extend the existing frontend source-contract tests so the new TS field and workspace notice logic are locked in.

### Task 1: Expose Current Plan Version From the Backend Session Contract

**Files:**
- Modify: `backend/models/agent.py`
- Modify: `backend/services/agent_read_service.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Write the failing backend regression tests**

Add these tests inside `SessionServiceBehaviorTests` in `tests/test_agent_persistence.py`:

```python
    def test_create_session_response_exposes_current_plan_version(self):
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")

        self.assertIsNotNone(session.plan)
        self.assertEqual(session.currentPlanVersion, 1)

    def test_add_user_message_after_plan_returns_incremented_current_plan_version(self):
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        initial = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        updated = service.add_user_message(initial.id, "整体再商务一点，目标受众改成销售团队")

        self.assertEqual(initial.currentPlanVersion, 1)
        self.assertIsNotNone(updated.plan)
        self.assertEqual(updated.currentPlanVersion, 2)

    def test_read_service_uses_current_plan_pointer_for_plan_and_version(self):
        from backend.db.repositories import AgentPlanRepository, AgentSessionRepository
        from backend.services.agent_read_service import AgentReadService
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        read_service = AgentReadService(session_factory=self.SessionLocal)

        initial = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        revised = service.add_user_message(initial.id, "整体再商务一点，目标受众改成销售团队")

        with self.SessionLocal() as db:
            plan_repo = AgentPlanRepository(db)
            session_repo = AgentSessionRepository(db)
            session_record = session_repo.get(initial.id)
            first_plan, second_plan = plan_repo.list_for_session(initial.id)
            session_record.current_plan_id = first_plan.id
            db.commit()

        reread = read_service.read_session(initial.id)

        self.assertEqual(reread.currentPlanVersion, 1)
        self.assertIsNotNone(reread.plan)
        self.assertEqual(reread.plan.style, initial.plan.style)
        self.assertNotEqual(reread.plan.style, revised.plan.style)
```

- [ ] **Step 2: Run the backend tests to confirm they fail first**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_create_session_response_exposes_current_plan_version \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_add_user_message_after_plan_returns_incremented_current_plan_version \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_service_uses_current_plan_pointer_for_plan_and_version -v
```

Expected:

- FAIL because `AgentSession` does not yet expose `currentPlanVersion`
- FAIL because `AgentReadService` still reads the latest plan row instead of the current plan pointer

- [ ] **Step 3: Implement the backend contract changes**

Update `backend/models/agent.py`:

```python
class AgentSession(BaseModel):
    id: str
    status: AgentStatus = AgentStatus.IDLE
    messages: List[AgentMessage] = Field(default_factory=list)
    plan: Optional[EditPlan] = None
    clips: List[ClipInfo] = Field(default_factory=list)
    events: List[AgentEvent] = Field(default_factory=list)
    steps: List[AgentStep] = Field(default_factory=list)
    videoUrl: Optional[str] = None
    activeJobId: Optional[str] = None
    grounding: Optional[AgentGroundingSummary] = None
    currentPlanVersion: int | None = None
    plannerTrace: Dict[str, Any] | None = None
    error: Optional[AgentError] = None
    progress: float = 0.0
    currentStep: str = ""
```

Update `backend/services/agent_read_service.py` so session reads use the current plan pointer:

```python
class AgentReadService:
    def read_session(self, session_id: str) -> AgentSession:
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            session_record = session_repo.get(session_id)
            if session_record is None:
                raise KeyError(session_id)

            current_plan_row = self.load_current_plan(db, session_record)

            return self.build_session_response(
                session_record=session_record,
                message_rows=message_repo.list_for_session(session_id),
                plan_row=current_plan_row,
                artifact_rows=self.load_artifacts(db, session_id),
                event_rows=AgentEventRepository(db).list_for_session(session_id),
            )

    def load_current_plan(self, db_session, session_record):
        if not session_record.current_plan_id:
            return None
        return AgentPlanRepository(db_session).get(session_record.current_plan_id)

    def build_session_response(self, session_record, message_rows, plan_row, artifact_rows, event_rows) -> AgentSession:
        plan = self._build_edit_plan(plan_row)
        clip_rows = [row for row in artifact_rows if row.artifact_type == "clip"]
        return AgentSession(
            id=session_record.id,
            status=AgentStatus(session_record.status),
            messages=[
                AgentMessage(
                    id=row.id,
                    role=row.role,
                    content=row.content,
                    createdAt=row.created_at.isoformat(),
                )
                for row in message_rows
            ],
            plan=plan,
            clips=[self._build_clip_info(row) for row in clip_rows],
            events=[event for event in self.build_event_response(event_rows)],
            steps=self.step_snapshot_service.build_session_steps(
                session_record=session_record,
                message_rows=message_rows,
                plan_row=plan_row,
                event_rows=event_rows,
            ),
            videoUrl=session_record.video_url,
            activeJobId=session_record.active_job_id,
            grounding=self._build_grounding_response(session_record),
            currentPlanVersion=getattr(plan_row, "version", None),
            plannerTrace=session_record.planner_trace_json or {},
            error=(
                AgentError(
                    message=session_record.error_message,
                    retryableStep=session_record.error_retryable_step,
                )
                if session_record.error_message
                else None
            ),
            progress=session_record.progress,
            currentStep=session_record.current_step or "",
        )
```

- [ ] **Step 4: Re-run the backend regression tests**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_create_session_response_exposes_current_plan_version \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_add_user_message_after_plan_returns_incremented_current_plan_version \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_service_uses_current_plan_pointer_for_plan_and_version -v
```

Expected:

- PASS
- `currentPlanVersion` returns `1` on the first plan
- `currentPlanVersion` returns `2` after revision
- forcing `current_plan_id` back to v1 makes the read service return v1 plan data and version

- [ ] **Step 5: Commit the backend contract work**

Run:

```bash
git add backend/models/agent.py backend/services/agent_read_service.py tests/test_agent_persistence.py
git commit -m "feat: expose current plan version in session response"
```

### Task 2: Show Revision Success Feedback in `/workspace`

**Files:**
- Modify: `src/lib/agentApi.ts`
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Test: `tests/test_agent_backend.py`

- [ ] **Step 1: Write the failing frontend source-contract test**

Add this test inside `FrontendClientContractTests` in `tests/test_agent_backend.py`:

```python
    def test_workspace_revision_feedback_uses_current_plan_version(self):
        api_source = (ROOT / "src" / "lib" / "agentApi.ts").read_text(encoding="utf-8")
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("currentPlanVersion: number | null", api_source)
        self.assertIn("const [showPlanUpdatedNotice, setShowPlanUpdatedNotice] = useState(false);", workspace_source)
        self.assertIn(
            "const basePlanVersion = session?.plan && typeof session.currentPlanVersion === 'number' ? session.currentPlanVersion : null;",
            workspace_source,
        )
        self.assertIn("nextSession.currentPlanVersion > basePlanVersion", workspace_source)
        self.assertIn("已根据你的修改更新计划", workspace_source)
```

- [ ] **Step 2: Run the frontend source-contract test and watch it fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_revision_feedback_uses_current_plan_version -v
```

Expected:

- FAIL because `currentPlanVersion` is missing from `src/lib/agentApi.ts`
- FAIL because `BriefWorkspacePage.tsx` has no version-based revision success notice yet

- [ ] **Step 3: Implement the frontend TypeScript contract and workspace notice**

Update `src/lib/agentApi.ts`:

```ts
export interface AgentSession {
  id: string
  status: AgentStatus
  messages: AgentMessage[]
  plan: EditPlan | null
  clips: ClipInfo[]
  events: AgentEvent[]
  steps: AgentStep[]
  videoUrl: string | null
  activeJobId: string | null
  progress: number
  currentStep: string
  grounding: AgentGroundingSummary | null
  currentPlanVersion: number | null
  error: AgentErrorInfo | null
}
```

Update `src/components/workspace/BriefWorkspacePage.tsx`:

```tsx
  const [showPlanUpdatedNotice, setShowPlanUpdatedNotice] = useState(false);

  useEffect(() => {
    setSelectedDirection('');
    setSelectedCandidateIds(session?.grounding?.selectedCandidateIds ?? []);
    setShowPlanUpdatedNotice(false);
  }, [session?.id]);

  useEffect(() => {
    if (session?.status && RUNNING_STATUSES.has(session.status)) {
      setShowPlanUpdatedNotice(false);
    }
  }, [session?.status]);

  const submitMessage = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSend) {
      return;
    }

    setSubmitting(true);
    setErrorText('');

    const basePlanVersion =
      session?.plan && typeof session.currentPlanVersion === 'number' ? session.currentPlanVersion : null;
    setShowPlanUpdatedNotice(false);

    try {
      const nextSession = session
        ? await sendAgentMessage(session.id, message)
        : await createAgentSession(message);
      setActiveSessionId(nextSession.id);
      setSession(nextSession);
      setShowPlanUpdatedNotice(
        basePlanVersion !== null &&
          typeof nextSession.currentPlanVersion === 'number' &&
          nextSession.currentPlanVersion > basePlanVersion
      );
      setMessage('');
    } catch (error) {
      setShowPlanUpdatedNotice(false);
      setErrorText(toUserError(error, () => setSession(null)));
    } finally {
      setSubmitting(false);
    }
  };
```

Render the inline notice inside the `finalize_plan` block, above the summary cards:

```tsx
                        {showPlanUpdatedNotice ? (
                          <div className="rounded-lg border border-[rgba(168,198,108,0.38)] bg-[#f6faef] px-3 py-2 text-sm font-semibold text-accentink">
                            已根据你的修改更新计划
                          </div>
                        ) : null}

                        <div className="grid gap-3">
```

- [ ] **Step 4: Re-run the frontend source-contract test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_revision_feedback_uses_current_plan_version -v
```

Expected:

- PASS
- Source contract now proves the TS client understands `currentPlanVersion`
- Source contract now proves `/workspace` compares the returned version before showing the success notice

- [ ] **Step 5: Commit the frontend feedback work**

Run:

```bash
git add src/lib/agentApi.ts src/components/workspace/BriefWorkspacePage.tsx tests/test_agent_backend.py
git commit -m "feat: show workspace plan update feedback"
```

### Task 3: Run Focused Regression Verification

**Files:**
- Modify: none
- Test: `tests/test_agent_persistence.py`
- Test: `tests/test_agent_backend.py`
- Verify: `package.json` build script via `npm run build`

- [ ] **Step 1: Run the focused Python regression suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_create_session_response_exposes_current_plan_version \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_add_user_message_after_plan_returns_incremented_current_plan_version \
  tests.test_agent_persistence.SessionServiceBehaviorTests.test_read_service_uses_current_plan_pointer_for_plan_and_version \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_revision_feedback_uses_current_plan_version -v
```

Expected:

- PASS
- Backend current-plan semantics and frontend notice contract both stay green together

- [ ] **Step 2: Run the Next.js build to catch TS or JSX regressions**

Run:

```bash
npm run build
```

Expected:

- PASS
- Next.js build completes without TypeScript or JSX errors

- [ ] **Step 3: Check the final diff before handing off**

Run:

```bash
git status --short
git diff -- backend/models/agent.py backend/services/agent_read_service.py tests/test_agent_persistence.py src/lib/agentApi.ts src/components/workspace/BriefWorkspacePage.tsx tests/test_agent_backend.py
```

Expected:

- Only the six planned files are modified
- No unrelated workspace or documentation files were changed

## Self-Review

- **Spec coverage:** Task 1 covers the backend `currentPlanVersion` contract and current-plan semantics. Task 2 covers the `/workspace` notice and TS client update. Task 3 covers the targeted Python regression and Next build verification required by the spec’s acceptance criteria.
- **Placeholder scan:** No `TODO`, `TBD`, or “implement later” placeholders remain. Every task has concrete files, code, commands, and expected outcomes.
- **Type consistency:** The same property name, `currentPlanVersion`, is used in the backend Pydantic model, the read service response, the TS client contract, the workspace component logic, and the source-contract tests.
