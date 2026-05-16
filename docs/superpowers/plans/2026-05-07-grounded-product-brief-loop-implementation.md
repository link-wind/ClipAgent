# Grounded Product Brief Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first agent-first workflow slice where `/workspace` turns a plain-text product brief into candidate real-product visuals, lets the user confirm those candidates, and then generates a grounded plan from the confirmed set before any render job is queued.

**Architecture:** Keep the existing `/api/agent/sessions -> /messages -> /confirm` session flow, but split planning into two phases: pre-confirmation grounding and post-confirmation execution. Add durable session-level grounding state in the backend, expose it through the existing `AgentSession` response, and render a new candidate confirmation step inside `BriefWorkspacePage` without trying to solve full hosted-beta concerns such as auth, object storage, or multi-user ownership in this slice.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, Python `unittest`, Next.js 14, React 18, TypeScript, Zustand, existing asset-provider modules (`fixture`, `youtube`, `pexels`), Node build verification.

---

## Scope Check

The approved design document covers more than one subsystem:

1. Agent grounding workflow
2. Hosted-beta platform requirements
3. Future storage and operational hardening

This implementation plan intentionally covers only the first subsystem:

- `brief -> candidate search -> user confirmation -> grounded plan`

It does **not** implement:

- authentication
- durable object storage
- full hosted-beta admin/settings work
- third-party licensing policy enforcement
- general web crawling beyond existing asset-provider primitives

Those should be separate follow-up plans after this grounded loop works end to end.

## File Structure

- Create: `backend/services/grounding_service.py`
  - Own brief parsing, candidate query building, provider fan-out, source labeling, and candidate-set assembly for the new grounding phase.
- Modify: `backend/models/agent.py`
  - Add typed models for candidate visuals, grounding summaries, confirmation payloads, and the session phase needed by frontend and API responses.
- Modify: `backend/db/models.py`
  - Add session-level persisted grounding columns and artifact typing for candidate visual state.
- Create: `backend/alembic/versions/20260507_add_agent_grounding_state.py`
  - Add migration for the new persistence columns.
- Modify: `backend/db/repositories/agent_sessions.py`
  - Add helper methods for updating grounding state on a session.
- Modify: `backend/db/repositories/agent_artifacts.py`
  - Add selectors for candidate-visual artifacts and confirmation-aware reads.
- Modify: `backend/services/agent_session_service.py`
  - Replace static immediate-plan creation with a grounding-aware flow that can create candidate sets and only build a grounded plan after confirmation.
- Modify: `backend/services/agent_read_service.py`
  - Map persisted grounding state and candidate artifacts back into the `AgentSession` response.
- Modify: `backend/services/agent_step_snapshot_service.py`
  - Replace the current generic planning step summaries with grounding-aware step results while preserving execution-step behavior.
- Modify: `backend/api/agent.py`
  - Add a confirmation endpoint for candidate visual selection and extend existing request models.
- Modify: `src/lib/agentApi.ts`
  - Add TypeScript contracts plus request helpers for candidate confirmation and grounded session reads.
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
  - Render the new candidate-confirmation state, prevent queue confirmation until candidates are confirmed, and show grounded-plan summaries.
- Modify: `src/stores/useAgentStore.ts`
  - Keep store shape aligned if the session contract grows and frontend needs local candidate-selection state.
- Modify: `tests/test_agent_backend.py`
  - Add backend contract tests for the grounding loop, new API endpoint behavior, and frontend source-contract assertions.
- Modify: `tests/test_agent_api_p0.py`
  - Extend session-step assertions for the new planning-phase semantics.
- Modify: `tests/test_agent_jobs.py`
  - Lock the updated queue-confirm contract so jobs only start after candidate confirmation.
- Modify: `tests/test_agent_persistence.py`
  - Cover new model columns, migration file presence, and repository contract additions.

Do not modify `/tasks` list/detail behavior in this slice.
Do not modify dashboard files in this slice.
Do not introduce external web-search providers in this slice; use existing provider primitives and explicit source metadata only.

---

### Task 1: Lock The New Grounding Contract With Failing Backend And Frontend Tests

**Files:**
- Modify: `tests/test_agent_backend.py`
- Modify: `tests/test_agent_api_p0.py`
- Modify: `tests/test_agent_jobs.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_api_p0.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Add a failing backend contract for session creation returning candidate visuals instead of a ready-to-queue plan**

In `tests/test_agent_backend.py`, inside `AgentApiTests`, after `test_create_session_api_returns_plan_ready_session`, add:

```python
    def test_create_session_api_returns_grounding_candidates_before_plan_confirmation(self):
        from backend.main import app

        client = _make_test_client(app)
        response = client.post("/api/agent/sessions", json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertIsNone(data["plan"])
        self.assertIn("grounding", data)
        self.assertEqual(data["grounding"]["status"], "needs_confirmation")
        self.assertGreater(len(data["grounding"]["candidates"]), 0)
```

- [ ] **Step 2: Add a failing backend contract for candidate confirmation producing a grounded plan**

In the same `AgentApiTests` class, add:

```python
    def test_confirm_candidates_api_builds_grounded_plan(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post(
            "/api/agent/sessions",
            json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
        ).json()

        candidate_ids = [candidate["id"] for candidate in created["grounding"]["candidates"][:2]]
        response = client.post(
            f"/api/agent/sessions/{created['id']}/grounding/confirm",
            json={"candidateIds": candidate_ids},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertEqual(data["grounding"]["status"], "confirmed")
        self.assertEqual(data["grounding"]["selectedCandidateIds"], candidate_ids)
        self.assertIsNotNone(data["plan"])
        self.assertGreater(len(data["plan"]["scenes"]), 0)
```

- [ ] **Step 3: Add a failing queueing contract so `/confirm` is rejected before candidate confirmation**

In `tests/test_agent_jobs.py`, inside `ConfirmFlowContractTests`, add:

```python
    def test_confirm_session_rejects_unconfirmed_grounding_state(self):
        from backend.services.agent_execution_service import AgentExecutionService

        session = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )

        with self.assertRaisesRegex(RuntimeError, "Session cannot be confirmed before grounding candidates are selected"):
            service.confirm_session(session.id)
```

- [ ] **Step 4: Add a failing step-snapshot contract for the new planning-phase results**

In `tests/test_agent_api_p0.py`, add:

```python
    def test_session_steps_show_candidate_confirmation_before_finalize_plan(self):
        session = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")

        self.assertEqual(session.steps[0].id, "understand_request")
        self.assertEqual(session.steps[0].status, "succeeded")
        self.assertEqual(session.steps[1].id, "extract_requirements")
        self.assertEqual(session.steps[1].status, "succeeded")
        self.assertEqual(session.steps[2].id, "generate_options")
        self.assertEqual(session.steps[2].status, "succeeded")
        self.assertEqual(session.steps[2].result["status"], "needs_confirmation")
        self.assertEqual(session.steps[3].id, "finalize_plan")
        self.assertEqual(session.steps[3].status, "pending")
```

- [ ] **Step 5: Add a failing frontend source-contract test for the candidate confirmation UI**

In `tests/test_agent_backend.py`, inside `FrontendClientContractTests`, after `test_workspace_handoff_renders_execution_steps_and_result_states`, add:

```python
    def test_workspace_renders_candidate_confirmation_stage(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("候选产品画面确认", workspace_source)
        self.assertIn("确认这些画面", workspace_source)
        self.assertIn("grounding", workspace_source)
        self.assertIn("selectedCandidateIds", workspace_source)
```

- [ ] **Step 6: Run the new tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentApiTests.test_create_session_api_returns_grounding_candidates_before_plan_confirmation \
  tests.test_agent_backend.AgentApiTests.test_confirm_candidates_api_builds_grounded_plan \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_renders_candidate_confirmation_stage \
  tests.test_agent_api_p0.SessionStepSnapshotTests.test_session_steps_show_candidate_confirmation_before_finalize_plan \
  tests.test_agent_jobs.ConfirmFlowContractTests.test_confirm_session_rejects_unconfirmed_grounding_state
```

Expected: FAIL because grounding models, confirmation endpoint, updated step results, and workspace candidate UI do not exist yet.

- [ ] **Step 7: Commit the failing-contract baseline**

```bash
git add tests/test_agent_backend.py tests/test_agent_api_p0.py tests/test_agent_jobs.py
git commit -m "test: lock grounded product brief loop contract"
```

---

### Task 2: Add Persistent Grounding Models And Migration

**Files:**
- Modify: `backend/models/agent.py`
- Modify: `backend/db/models.py`
- Create: `backend/alembic/versions/20260507_add_agent_grounding_state.py`
- Modify: `tests/test_agent_persistence.py`
- Test: `tests/test_agent_persistence.py`

- [ ] **Step 1: Add failing persistence assertions for new session grounding columns**

In `tests/test_agent_persistence.py`, extend `test_agent_persistence_models_expose_required_columns` so `AgentSessionRecord` is expected to include:

```python
                "grounding_status",
                "grounding_summary_json",
                "selected_candidate_ids_json",
```

and extend `test_initial_migration_mentions_core_tables_and_indexes` to assert the new migration filename exists:

```python
        grounding_migration = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260507_add_agent_grounding_state.py"
        )
        self.assertTrue(grounding_migration.exists())
```

- [ ] **Step 2: Run the persistence test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.AgentPersistenceModelTests.test_agent_persistence_models_expose_required_columns \
  tests.test_agent_persistence.AlembicPersistenceTests.test_initial_migration_mentions_core_tables_and_indexes
```

Expected: FAIL because the columns and migration file do not exist yet.

- [ ] **Step 3: Add grounded-session response models in `backend/models/agent.py`**

Insert these models after `AgentError`:

```python
class AgentGroundingCandidate(BaseModel):
    id: str
    title: str
    sourceUrl: str
    previewUrl: str = ""
    sourceType: str
    provider: str
    providerLabel: str
    isOfficial: bool = False
    confidence: float = 0.0
    summary: str = ""
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class AgentGroundingSummary(BaseModel):
    status: Literal["pending_search", "needs_confirmation", "confirmed"] = "pending_search"
    productName: str = ""
    audience: str = ""
    styleHint: str = ""
    featureHints: List[str] = Field(default_factory=list)
    searchQueries: List[str] = Field(default_factory=list)
    candidates: List[AgentGroundingCandidate] = Field(default_factory=list)
    selectedCandidateIds: List[str] = Field(default_factory=list)
```

and add `grounding: Optional[AgentGroundingSummary] = None` to `AgentSession`.

- [ ] **Step 4: Add session grounding columns in `backend/db/models.py`**

Update `AgentSessionRecord` to include:

```python
    grounding_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    grounding_summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    selected_candidate_ids_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 5: Create the Alembic migration**

Create `backend/alembic/versions/20260507_add_agent_grounding_state.py` with:

```python
"""add agent grounding state

Revision ID: 20260507_add_agent_grounding_state
Revises: 20260502_create_agent_tables
Create Date: 2026-05-07 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_add_agent_grounding_state"
down_revision = "20260502_create_agent_tables"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("agent_sessions", sa.Column("grounding_status", sa.String(length=32), nullable=True))
    op.add_column("agent_sessions", sa.Column("grounding_summary_json", sa.JSON(), nullable=True))
    op.add_column("agent_sessions", sa.Column("selected_candidate_ids_json", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("agent_sessions", "selected_candidate_ids_json")
    op.drop_column("agent_sessions", "grounding_summary_json")
    op.drop_column("agent_sessions", "grounding_status")
```

- [ ] **Step 6: Run the persistence tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.AgentPersistenceModelTests.test_agent_persistence_models_expose_required_columns \
  tests.test_agent_persistence.AlembicPersistenceTests.test_initial_migration_mentions_core_tables_and_indexes
```

Expected: PASS.

- [ ] **Step 7: Commit the grounding model layer**

```bash
git add backend/models/agent.py backend/db/models.py backend/alembic/versions/20260507_add_agent_grounding_state.py tests/test_agent_persistence.py
git commit -m "feat: add persistent agent grounding state"
```

---

### Task 3: Implement Backend Grounding Search And Confirmation Flow

**Files:**
- Create: `backend/services/grounding_service.py`
- Modify: `backend/db/repositories/agent_sessions.py`
- Modify: `backend/db/repositories/agent_artifacts.py`
- Modify: `backend/services/agent_session_service.py`
- Modify: `backend/services/agent_read_service.py`
- Modify: `backend/api/agent.py`
- Modify: `tests/test_agent_backend.py`
- Modify: `tests/test_agent_jobs.py`
- Test: `tests/test_agent_backend.py`
- Test: `tests/test_agent_jobs.py`

- [ ] **Step 1: Add a failing repository-contract assertion for new helper methods**

In `tests/test_agent_persistence.py`, inside `RepositoryContractTests.test_repositories_expose_minimal_methods`, add:

```python
        self.assertTrue(callable(getattr(AgentSessionRepository, "update_grounding_state", None)))
        self.assertTrue(callable(getattr(AgentArtifactRepository, "list_candidate_visuals_for_session", None)))
```

- [ ] **Step 2: Run the repository contract test and verify it fails**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_persistence.RepositoryContractTests.test_repositories_expose_minimal_methods
```

Expected: FAIL because the repository methods do not exist yet.

- [ ] **Step 3: Create `backend/services/grounding_service.py`**

Create the file with this initial implementation:

```python
from __future__ import annotations

from dataclasses import dataclass

from backend.models.agent import AgentGroundingCandidate, AgentGroundingSummary
from backend.services.asset_providers.fixture import search_fixture_candidates
from backend.services.asset_providers.pexels import search_pexels_candidates
from backend.services.asset_providers.youtube import search_youtube_candidates


@dataclass(frozen=True)
class ParsedBrief:
    product_name: str
    audience: str
    style_hint: str
    feature_hints: list[str]
    search_queries: list[str]


class GroundingService:
    def parse_brief(self, prompt: str) -> ParsedBrief:
        text = (prompt or "").strip()
        product_name = text.split("做", 1)[-1].replace("一个", "").strip() if text else "未命名产品"
        feature_hints = [segment.strip(" ，,。；;") for segment in text.split("，") if segment.strip()]
        queries = [product_name] if product_name else []
        if feature_hints:
            queries.extend(feature_hints[:2])
        return ParsedBrief(
            product_name=product_name or "未命名产品",
            audience="品牌运营 / 小团队市场",
            style_hint="产品介绍 / 功能亮点",
            feature_hints=feature_hints[:4],
            search_queries=[query for query in queries if query],
        )

    def build_grounding_summary(self, prompt: str) -> AgentGroundingSummary:
        parsed = self.parse_brief(prompt)
        candidates = self.search_candidates(parsed.search_queries)
        return AgentGroundingSummary(
            status="needs_confirmation",
            productName=parsed.product_name,
            audience=parsed.audience,
            styleHint=parsed.style_hint,
            featureHints=parsed.feature_hints,
            searchQueries=parsed.search_queries,
            candidates=candidates,
            selectedCandidateIds=[],
        )

    def search_candidates(self, search_queries: list[str]) -> list[AgentGroundingCandidate]:
        joined = " ".join(search_queries).strip()
        keywords = [part for part in joined.split() if part]
        raw_candidates = [
            *search_fixture_candidates(keywords, max_results=2),
            *search_youtube_candidates(keywords, max_results=3),
            *search_pexels_candidates(keywords, max_results=2),
        ]
        candidates: list[AgentGroundingCandidate] = []
        for index, candidate in enumerate(raw_candidates, start=1):
            provider = candidate.provider
            source_url = candidate.source_url
            title = candidate.title or candidate.id or f"{provider}-{index}"
            candidates.append(
                AgentGroundingCandidate(
                    id=f"{provider}:{candidate.id or index}",
                    title=title,
                    sourceUrl=source_url,
                    previewUrl=candidate.thumbnail or source_url,
                    sourceType="video",
                    provider=provider,
                    providerLabel=provider.upper(),
                    isOfficial=False,
                    confidence=max(0.2, 1.0 - (index - 1) * 0.1),
                    summary=title,
                    diagnostics=candidate.to_metadata(),
                )
            )
        return candidates[:6]


grounding_service = GroundingService()
```

- [ ] **Step 4: Add session and artifact repository helpers**

In `backend/db/repositories/agent_sessions.py`, add:

```python
    def update_grounding_state(
        self,
        session_id: str,
        *,
        grounding_status: str,
        grounding_summary_json: dict | None,
        selected_candidate_ids_json: list[str] | None,
    ) -> AgentSessionRecord:
        record = self.get(session_id)
        if record is None:
            raise KeyError(session_id)
        record.grounding_status = grounding_status
        record.grounding_summary_json = grounding_summary_json
        record.selected_candidate_ids_json = selected_candidate_ids_json
        self.db.flush()
        self.db.refresh(record)
        return record
```

In `backend/db/repositories/agent_artifacts.py`, add:

```python
    def list_candidate_visuals_for_session(self, session_id: str) -> list[AgentArtifactRecord]:
        stmt = (
            select(AgentArtifactRecord)
            .where(
                AgentArtifactRecord.session_id == session_id,
                AgentArtifactRecord.artifact_type == "candidate_visual",
            )
            .order_by(AgentArtifactRecord.created_at.asc(), AgentArtifactRecord.id.asc())
        )
        return list(self.db.scalars(stmt))
```

- [ ] **Step 5: Update `AgentSessionService.create_session` to build grounding state instead of an immediate plan**

Replace the prompt branch in `create_session` with logic that:

1. stores the user message
2. calls `grounding_service.build_grounding_summary(prompt)`
3. updates session state to `status="plan_ready"`, `current_step="等待确认候选产品画面"`, `progress=20`
4. persists grounding fields on the session
5. appends an assistant message like `我已经理解了你的 brief，并找到了候选产品画面，请先确认正确的素材。`

Do **not** create an `AgentPlanRecord` yet in this branch.

- [ ] **Step 6: Add a candidate-confirmation method to `AgentSessionService`**

Add:

```python
    def confirm_grounding_candidates(self, session_id: str, candidate_ids: list[str]) -> AgentSession:
        if not candidate_ids:
            raise ValueError("At least one candidate must be selected")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            plan_repo = AgentPlanRepository(db)

            try:
                session_record = session_repo.get(session_id)
                if session_record is None:
                    raise KeyError(session_id)

                grounding_summary = session_record.grounding_summary_json or {}
                grounding = AgentGroundingSummary.model_validate(grounding_summary)
                allowed_ids = {candidate.id for candidate in grounding.candidates}
                invalid_ids = [candidate_id for candidate_id in candidate_ids if candidate_id not in allowed_ids]
                if invalid_ids:
                    raise ValueError(f"Unknown candidate ids: {', '.join(invalid_ids)}")

                updated_grounding = grounding.model_copy(
                    update={
                        "status": "confirmed",
                        "selectedCandidateIds": candidate_ids,
                    }
                )
                session_repo.update_grounding_state(
                    session_id,
                    grounding_status="confirmed",
                    grounding_summary_json=updated_grounding.model_dump(mode="json"),
                    selected_candidate_ids_json=candidate_ids,
                )

                plan = self._build_grounded_plan_from_candidates(updated_grounding)
                self._apply_plan_to_session(session_record, plan)
                latest_plan = plan_repo.get_latest_for_session(session_id)
                next_version = 1 if latest_plan is None else latest_plan.version + 1
                plan_repo.create(
                    session_id=session_id,
                    version=next_version,
                    title=plan.title,
                    target_duration=int(plan.targetDuration),
                    style=plan.style,
                    plan_json=plan.model_dump(mode="json"),
                )
                message_repo.create(
                    session_id=session_id,
                    role="assistant",
                    content="我已经根据你确认的产品画面生成 grounded 方案，你可以继续修改或确认开始。",
                )
                db.commit()
            except Exception:
                db.rollback()
                raise

        return self.read_service.read_session(session_id)
```

- [ ] **Step 7: Add `_build_grounded_plan_from_candidates` in `AgentSessionService`**

Add:

```python
    def _build_grounded_plan_from_candidates(self, grounding) -> EditPlan:
        confirmed = [candidate for candidate in grounding.candidates if candidate.id in grounding.selectedCandidateIds]
        scenes: list[PlanScene] = []
        for index, candidate in enumerate(confirmed[:4], start=1):
            title = candidate.title or grounding.productName
            query = grounding.searchQueries[min(index - 1, len(grounding.searchQueries) - 1)] if grounding.searchQueries else grounding.productName
            scenes.append(
                PlanScene(
                    id=index,
                    description=f"围绕 {title} 展示产品功能亮点",
                    keywords=[grounding.productName, *grounding.featureHints[:2]],
                    duration=6 if index < 4 else 8,
                    searchQuery=query,
                )
            )
        if not scenes:
            scenes.append(
                PlanScene(
                    id=1,
                    description=f"展示 {grounding.productName} 的核心界面与卖点",
                    keywords=[grounding.productName],
                    duration=8,
                    searchQuery=grounding.productName,
                )
            )
        return EditPlan(
            title=f"{grounding.productName} 产品亮点短片",
            targetDuration=30,
            style=grounding.styleHint or "产品介绍 / 功能亮点",
            scenes=scenes,
        )
```

- [ ] **Step 8: Extend `AgentReadService.build_session_response` to return grounding**

Import `AgentGroundingSummary` and add:

```python
        grounding = (
            AgentGroundingSummary.model_validate(session_record.grounding_summary_json)
            if session_record.grounding_summary_json
            else None
        )
```

then include `grounding=grounding` in the returned `AgentSession`.

- [ ] **Step 9: Add the new API request model and endpoint**

In `backend/api/agent.py`, add:

```python
class GroundingConfirmRequest(BaseModel):
    candidateIds: list[str]
```

and the endpoint:

```python
@router.post("/sessions/{session_id}/grounding/confirm", response_model=AgentSession)
async def confirm_grounding(session_id: str, request: GroundingConfirmRequest):
    try:
        session = session_service.confirm_grounding_candidates(session_id, request.candidateIds)
        return agent_service.sync_session(session)
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
```

- [ ] **Step 10: Guard `AgentExecutionService.confirm_session`**

Before reading the latest plan, add:

```python
                if session_record.grounding_status != "confirmed":
                    raise RuntimeError("Session cannot be confirmed before grounding candidates are selected")
```

- [ ] **Step 11: Run the grounding backend tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.AgentApiTests.test_create_session_api_returns_grounding_candidates_before_plan_confirmation \
  tests.test_agent_backend.AgentApiTests.test_confirm_candidates_api_builds_grounded_plan \
  tests.test_agent_jobs.ConfirmFlowContractTests.test_confirm_session_rejects_unconfirmed_grounding_state \
  tests.test_agent_persistence.RepositoryContractTests.test_repositories_expose_minimal_methods
```

Expected: PASS.

- [ ] **Step 12: Commit the backend grounding flow**

```bash
git add backend/services/grounding_service.py backend/db/repositories/agent_sessions.py backend/db/repositories/agent_artifacts.py backend/services/agent_session_service.py backend/services/agent_read_service.py backend/api/agent.py backend/services/agent_execution_service.py tests/test_agent_backend.py tests/test_agent_jobs.py tests/test_agent_persistence.py
git commit -m "feat: add candidate grounding flow for agent sessions"
```

---

### Task 4: Make Step Snapshots Reflect The Grounded Planning Phase

**Files:**
- Modify: `backend/services/agent_step_snapshot_service.py`
- Modify: `tests/test_agent_api_p0.py`
- Test: `tests/test_agent_api_p0.py`

- [ ] **Step 1: Update the `generate_options` step result to represent candidate confirmation**

In `backend/services/agent_step_snapshot_service.py`, replace the old `generate_options` result builder usage for session steps with:

```python
    def _build_generate_options_result_from_grounding(self, grounding) -> dict[str, Any]:
        return {
            "status": grounding.status,
            "productName": grounding.productName,
            "searchQueries": grounding.searchQueries,
            "selectedCandidateIds": grounding.selectedCandidateIds,
            "options": [
                {
                    "id": candidate.id,
                    "title": candidate.title,
                    "description": candidate.summary,
                    "searchQuery": candidate.sourceUrl,
                    "keywords": [candidate.providerLabel, "official" if candidate.isOfficial else "third-party"],
                    "duration": 0,
                    "previewUrl": candidate.previewUrl,
                    "sourceType": candidate.sourceType,
                    "confidence": candidate.confidence,
                }
                for candidate in grounding.candidates
            ],
        }
```

- [ ] **Step 2: Hold `finalize_plan` as pending until a real plan exists**

In `build_session_steps`, only mark `finalize_plan` succeeded when `plan is not None`. When `plan is None` but grounding exists, keep `finalize_plan` pending and set:

```python
        steps_by_id["generate_options"] = self._build_succeeded_step(
            self._meta("generate_options"),
            self._build_generate_options_result_from_grounding(grounding),
            summary="已生成候选产品画面，等待确认",
        )
```

- [ ] **Step 3: Make `extract_requirements` use grounding summary when no plan exists**

Add a helper:

```python
    def _build_requirements_result_from_grounding(self, prompt: Optional[str], grounding) -> dict[str, Any]:
        return {
            "originalPrompt": prompt or "",
            "title": grounding.productName,
            "targetDuration": 30,
            "style": grounding.styleHint,
            "sceneCount": 0,
        }
```

and use it in the session-step build when `grounding` exists but `plan` is still `None`.

- [ ] **Step 4: Thread grounding into `build_session_steps`**

In `build_session_steps`, derive:

```python
        grounding = self._extract_grounding(session_record)
```

with helper:

```python
    def _extract_grounding(self, session_record):
        summary = getattr(session_record, "grounding_summary_json", None)
        if not summary:
            return None
        from backend.models.agent import AgentGroundingSummary
        return AgentGroundingSummary.model_validate(summary)
```

- [ ] **Step 5: Run the session-step contract test**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_api_p0.SessionStepSnapshotTests.test_session_steps_show_candidate_confirmation_before_finalize_plan
```

Expected: PASS.

- [ ] **Step 6: Commit the updated planning-step semantics**

```bash
git add backend/services/agent_step_snapshot_service.py tests/test_agent_api_p0.py
git commit -m "feat: reflect grounding confirmation in session step snapshots"
```

---

### Task 5: Add Frontend Candidate Confirmation And Queue Guard

**Files:**
- Modify: `src/lib/agentApi.ts`
- Modify: `src/stores/useAgentStore.ts`
- Modify: `src/components/workspace/BriefWorkspacePage.tsx`
- Modify: `tests/test_agent_backend.py`
- Test: `tests/test_agent_backend.py`
- Test: `npm run build`

- [ ] **Step 1: Add TypeScript grounding contracts and request helper**

In `src/lib/agentApi.ts`, add:

```ts
export interface AgentGroundingCandidate {
  id: string
  title: string
  sourceUrl: string
  previewUrl: string
  sourceType: string
  provider: string
  providerLabel: string
  isOfficial: boolean
  confidence: number
  summary: string
  diagnostics: Record<string, unknown>
}

export interface AgentGroundingSummary {
  status: 'pending_search' | 'needs_confirmation' | 'confirmed'
  productName: string
  audience: string
  styleHint: string
  featureHints: string[]
  searchQueries: string[]
  candidates: AgentGroundingCandidate[]
  selectedCandidateIds: string[]
}
```

Add `grounding: AgentGroundingSummary | null` to `AgentSession`, and add:

```ts
export function confirmGroundingCandidates(sessionId: string, candidateIds: string[]): Promise<AgentSession> {
  const encodedSessionId = encodeURIComponent(sessionId)

  return requestJson<AgentSession>(`/api/agent/sessions/${encodedSessionId}/grounding/confirm`, {
    method: 'POST',
    body: { candidateIds },
  })
}
```

- [ ] **Step 2: Add local candidate selection state in `BriefWorkspacePage.tsx`**

Add:

```tsx
  const [selectedCandidateIds, setSelectedCandidateIds] = useState<string[]>([])
```

and sync it from the session:

```tsx
  useEffect(() => {
    setSelectedCandidateIds(session?.grounding?.selectedCandidateIds ?? [])
  }, [session?.id, session?.grounding?.selectedCandidateIds])
```

- [ ] **Step 3: Replace the generic `generate_options` cards with candidate confirmation UI**

Inside the `step.id === 'generate_options'` branch, render a `候选产品画面确认` block using `session?.grounding?.candidates ?? []` and checkbox-style cards. Each card should show:

- title
- provider label
- confidence
- preview/source URL
- summary

The section heading should include the exact strings:

```tsx
<span className="mb-1.5 block text-xs font-extrabold text-secondary">候选产品画面确认</span>
<h3 className="text-[15px] font-semibold leading-snug text-ink">确认这些画面是否对应你要的视频产品</h3>
```

- [ ] **Step 4: Add a confirm-candidates action**

Add:

```tsx
  const confirmGrounding = async () => {
    if (!session || !selectedCandidateIds.length || isSubmitting) {
      return
    }

    setSubmitting(true)
    setErrorText('')

    try {
      const nextSession = await confirmGroundingCandidates(session.id, selectedCandidateIds)
      setActiveSessionId(nextSession.id)
      setSession(nextSession)
    } catch (error) {
      setErrorText(toUserError(error, () => setSession(null)))
    } finally {
      setSubmitting(false)
    }
  }
```

- [ ] **Step 5: Disable queue confirmation until grounding is confirmed**

Change:

```tsx
  const canConfirm = session?.status === 'plan_ready' && !isSubmitting;
```

to:

```tsx
  const canConfirm =
    session?.status === 'plan_ready' &&
    session?.grounding?.status === 'confirmed' &&
    !isSubmitting;
```

and add a separate `canConfirmGrounding` boolean:

```tsx
  const canConfirmGrounding =
    session?.status === 'plan_ready' &&
    session?.grounding?.status === 'needs_confirmation' &&
    selectedCandidateIds.length > 0 &&
    !isSubmitting;
```

- [ ] **Step 6: Wire the candidate confirmation button into the UI**

In the `generate_options` block footer, use:

```tsx
<div className="flex flex-wrap gap-2.5">
  <Button type="button" variant="secondary" disabled={!session}>
    继续修改
  </Button>
  <Button type="button" onClick={confirmGrounding} disabled={!canConfirmGrounding}>
    确认这些画面
  </Button>
</div>
```

- [ ] **Step 7: Run the frontend source-contract test and the build**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend.FrontendClientContractTests.test_workspace_renders_candidate_confirmation_stage
npm run build
```

Expected: PASS.

- [ ] **Step 8: Commit the workspace candidate confirmation UI**

```bash
git add src/lib/agentApi.ts src/stores/useAgentStore.ts src/components/workspace/BriefWorkspacePage.tsx tests/test_agent_backend.py
git commit -m "feat: add workspace candidate confirmation stage"
```

---

### Task 6: Run Focused Verification And Update The Spec/Plan Trail

**Files:**
- Verify: `tests/test_agent_backend.py`
- Verify: `tests/test_agent_api_p0.py`
- Verify: `tests/test_agent_jobs.py`
- Verify: `tests/test_agent_persistence.py`
- Verify: `docs/superpowers/specs/2026-05-07-agent-first-hosted-beta-design.md`
- Verify: `docs/superpowers/plans/2026-05-07-grounded-product-brief-loop-implementation.md`

- [ ] **Step 1: Run the focused Python suites**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest \
  tests.test_agent_backend \
  tests.test_agent_api_p0 \
  tests.test_agent_jobs \
  tests.test_agent_persistence
```

Expected: PASS.

- [ ] **Step 2: Run the frontend build**

Run:

```bash
npm run build
```

Expected: PASS.

- [ ] **Step 3: Confirm the implementation still matches the approved design scope**

Review:

```bash
sed -n '1,260p' docs/superpowers/specs/2026-05-07-agent-first-hosted-beta-design.md
sed -n '1,320p' docs/superpowers/plans/2026-05-07-grounded-product-brief-loop-implementation.md
```

Expected: implementation remains limited to the grounded product brief loop, with auth, object storage, and larger hosted-beta concerns intentionally deferred.

- [ ] **Step 4: Commit final verification notes if documentation changed during execution**

If execution required any plan/doc edits:

```bash
git add docs/superpowers/specs/2026-05-07-agent-first-hosted-beta-design.md docs/superpowers/plans/2026-05-07-grounded-product-brief-loop-implementation.md
git commit -m "docs: align grounded loop plan with implementation"
```

If no documentation changed, skip this commit.
