# LangChain User Revision Replan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `LangChainPlannerRuntime.replan_after_user_revision(...)` truly model-driven with a conservative patch contract, while preserving the existing `/workspace` revision flow and falling back to deterministic replanning when LangChain revision output is unsafe or unavailable.

**Architecture:** Add a revision-specific structured output contract in `planner_models.py`, teach `planner_runtime_langchain.py` to build revision prompts, parse and validate patch-only results, then merge those patches onto deep copies of the current `AgentPlan + ExecutionPlan`. Keep `planner_graph.py`, `PlannerOrchestrator`, and `AgentSessionService` externally stable, but enrich planner trace persistence so the latest revision runtime path records whether LangChain succeeded or deterministic fallback was used.

**Tech Stack:** FastAPI, Pydantic v2, LangChain, langchain-openai, LangGraph, SQLAlchemy, unittest

---

## File Structure

### Modified files

- Modify: `backend/services/planner_models.py`
  - Add revision-specific structured output models: `RevisionScenePatch` and `RevisionPlanningResult`
- Modify: `backend/services/planner_runtime_langchain.py`
  - Implement revision prompt building, structured output invocation, merge logic, validation, and deterministic fallback
- Modify: `backend/services/planner_orchestrator.py`
  - Record revision runtime source and fallback diagnostics in `planner_trace_json`
- Modify: `tests/test_planner_models.py`
  - Add contract coverage for revision patch models
- Modify: `tests/test_planner_runtime.py`
  - Add LangChain revision merge and fallback coverage
- Modify: `tests/test_planner_graph.py`
  - Keep graph-level revision replan coverage aligned with LangChain runtime wiring
- Modify: `tests/test_agent_planner_phase3.py`
  - Verify persisted vNext includes revision runtime trace and merged plan changes
- Modify: `tests/test_agent_persistence.py`
  - Verify fallback still persists a new plan version and updates current plan / observation linkage

## Scope Guardrails

- Do not change the external `/api/agent/sessions/{id}/messages` contract.
- Do not modify `planner_graph.py` or `AgentSessionService` entrypoint behavior unless a test proves a trace field is missing from the returned session.
- Do not change `OpenAIPlannerRuntime`; this phase is only about `LangChainPlannerRuntime`.
- Do not allow revision replanning to change scene count, scene ids, scene durations, or `ExecutionPlan.targetDuration`.
- Do not let model output override explicit `sceneKeywordUpdates`; those remain hard constraints from the user message parser.
- If LangChain revision output is missing, invalid, or unsafe to merge, fall back to `DeterministicPlannerRuntime.replan_after_user_revision(...)`.

### Task 1: Add the revision patch contract

**Files:**
- Modify: `backend/services/planner_models.py`
- Modify: `tests/test_planner_models.py`

- [ ] **Step 1: Write the failing planner model tests**

Add these tests to `tests/test_planner_models.py` inside `PlannerModelTests`:

```python
    def test_revision_scene_patch_defaults(self):
        from backend.services.planner_models import RevisionScenePatch

        patch = RevisionScenePatch(id=1)

        self.assertEqual(patch.id, 1)
        self.assertEqual(patch.description, "")
        self.assertEqual(patch.keywords, [])
        self.assertEqual(patch.searchQuery, "")

    def test_revision_planning_result_wraps_scene_patches(self):
        from backend.services.planner_models import RevisionPlanningResult

        result = RevisionPlanningResult(
            summary="整体更偏商务演示",
            audience="销售团队",
            styleHint="商务演示风格",
            style="商务演示风格",
            changeSummary="已根据最新修改意见完成计划重写",
            scenePatches=[
                {
                    "id": 1,
                    "description": "城市节奏感开场，建立商务氛围",
                    "keywords": ["city", "traffic", "dusk"],
                    "searchQuery": "city traffic dusk",
                }
            ],
        )

        self.assertEqual(result.audience, "销售团队")
        self.assertEqual(result.scenePatches[0].id, 1)
        self.assertEqual(result.scenePatches[0].searchQuery, "city traffic dusk")
```

- [ ] **Step 2: Run the focused planner model tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models.PlannerModelTests.test_revision_scene_patch_defaults tests.test_planner_models.PlannerModelTests.test_revision_planning_result_wraps_scene_patches -v
```

Expected: FAIL because `RevisionScenePatch` and `RevisionPlanningResult` do not exist yet.

- [ ] **Step 3: Add the revision patch models**

Update `backend/services/planner_models.py` by adding these models after `InitialPlanningResult`:

```python
class RevisionScenePatch(BaseModel):
    id: int
    description: str = ""
    keywords: list[str] = Field(default_factory=list)
    searchQuery: str = ""


class RevisionPlanningResult(BaseModel):
    summary: str = ""
    audience: str = ""
    styleHint: str = ""
    style: str = ""
    openIssues: list[dict[str, Any]] = Field(default_factory=list)
    changeSummary: str
    scenePatches: list[RevisionScenePatch] = Field(default_factory=list)
```

Keep the existing `UserRevisionFeedback` contract unchanged in this task.

- [ ] **Step 4: Run the focused planner model tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models.PlannerModelTests.test_revision_scene_patch_defaults tests.test_planner_models.PlannerModelTests.test_revision_planning_result_wraps_scene_patches -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/services/planner_models.py tests/test_planner_models.py
git commit -m "feat: add revision planning patch contract"
```

### Task 2: Implement LangChain revision replanning merge and fallback

**Files:**
- Modify: `backend/services/planner_runtime_langchain.py`
- Modify: `tests/test_planner_runtime.py`

- [ ] **Step 1: Add the failing LangChain revision runtime tests**

Append these tests to `tests/test_planner_runtime.py` inside `PlannerRuntimeTests`:

```python
    def test_langchain_runtime_replans_after_user_revision_with_patch_merge(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 1,
                        "description": "城市与车流开场，建立商务节奏",
                        "keywords": ["office", "lobby", "team"],
                        "searchQuery": "office lobby team",
                    }
                ],
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        next_agent, next_execution, change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点，目标受众改成销售团队",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(change_summary, "已根据最新修改意见完成计划重写")
        self.assertEqual(next_agent.summary, "更偏商务演示与销售沟通的版本")
        self.assertEqual(next_agent.understanding.audience, "销售团队")
        self.assertEqual(next_agent.understanding.styleHint, "商务演示风格")
        self.assertEqual(next_execution.style, "商务演示风格")
        self.assertEqual(next_agent.scenes[0].description, "城市与车流开场，建立商务节奏")
        self.assertEqual(next_execution.scenes[0].searchQuery, "office lobby team")
        self.assertEqual(next_execution.scenes[1].searchQuery, current_execution.scenes[1].searchQuery)
        self.assertEqual(next_execution.scenes[0].duration, current_execution.scenes[0].duration)
        self.assertEqual(next_execution.targetDuration, current_execution.targetDuration)
        self.assertEqual(next_agent.replanHistory[-1]["triggerType"], "user_revision")
        self.assertEqual(next_agent.replanHistory[-1]["summary"], "已根据最新修改意见完成计划重写")
        self.assertEqual(next_agent.replanHistory[-1]["runtime"], "langchain")

    def test_langchain_runtime_preserves_explicit_scene_keyword_updates_over_model_patch(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 1,
                        "description": "城市与车流开场，建立商务节奏",
                        "keywords": ["office", "lobby", "team"],
                        "searchQuery": "office lobby team",
                    }
                ],
            )
        )

        runtime = LangChainPlannerRuntime(model_name="gpt-4o-mini", llm=fake_llm)
        next_agent, next_execution, _change_summary = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点，目标受众改成销售团队，场景1：城市 车流 黄昏",
                sceneKeywordUpdates={1: ["城市", "车流", "黄昏"]},
            ),
        )

        self.assertEqual(next_agent.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(next_execution.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(next_execution.scenes[0].searchQuery, "城市 车流 黄昏")
        self.assertEqual(next_agent.scenes[0].description, "城市与车流开场，建立商务节奏")

    def test_langchain_runtime_falls_back_to_deterministic_revision_when_patch_targets_unknown_scene(self):
        from backend.services.planner_models import RevisionPlanningResult, UserRevisionFeedback
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        deterministic_delegate = Mock()
        deterministic_delegate.replan_after_user_revision.return_value = (
            "agent-fallback",
            "execution-fallback",
            "fallback summary",
        )
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )
        fake_llm = _FakeChatModel(
            result=RevisionPlanningResult(
                summary="更偏商务演示与销售沟通的版本",
                audience="销售团队",
                styleHint="商务演示风格",
                style="商务演示风格",
                changeSummary="已根据最新修改意见完成计划重写",
                scenePatches=[
                    {
                        "id": 99,
                        "description": "不存在的场景 patch",
                        "keywords": ["bad"],
                        "searchQuery": "bad",
                    }
                ],
            )
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=fake_llm,
            deterministic_delegate=deterministic_delegate,
        )
        result = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(result, ("agent-fallback", "execution-fallback", "fallback summary"))
        deterministic_delegate.replan_after_user_revision.assert_called_once()

    def test_langchain_runtime_falls_back_to_deterministic_revision_when_model_raises(self):
        from backend.services.planner_models import UserRevisionFeedback
        from backend.services.planner_runtime_langchain import LangChainPlannerRuntime
        from backend.services.planner_runtime_deterministic import DeterministicPlannerRuntime

        deterministic_delegate = Mock()
        deterministic_delegate.replan_after_user_revision.return_value = (
            "agent-fallback",
            "execution-fallback",
            "fallback summary",
        )
        current_agent, current_execution = DeterministicPlannerRuntime().build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        runtime = LangChainPlannerRuntime(
            model_name="gpt-4o-mini",
            llm=_FakeChatModel(error=RuntimeError("revision planning failed")),
            deterministic_delegate=deterministic_delegate,
        )
        result = runtime.replan_after_user_revision(
            current_agent=current_agent,
            current_execution=current_execution,
            revision_feedback=UserRevisionFeedback(
                message="整体再商务一点",
                sceneKeywordUpdates={},
            ),
        )

        self.assertEqual(result, ("agent-fallback", "execution-fallback", "fallback summary"))
        deterministic_delegate.replan_after_user_revision.assert_called_once()
```

- [ ] **Step 2: Run the focused LangChain revision runtime tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_replans_after_user_revision_with_patch_merge tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_preserves_explicit_scene_keyword_updates_over_model_patch tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_falls_back_to_deterministic_revision_when_patch_targets_unknown_scene tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_falls_back_to_deterministic_revision_when_model_raises -v
```

Expected: FAIL because `planner_runtime_langchain.py` still delegates revision replanning directly to deterministic runtime.

- [ ] **Step 3: Add revision prompt and runnable helpers**

Update `backend/services/planner_runtime_langchain.py`:

1. Extend the imports:

```python
from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
    InitialPlanningResult,
    RevisionPlanningResult,
    SearchExecutionFeedback,
    UserRevisionFeedback,
)
```

2. Add a revision system prompt after `INITIAL_PLANNER_SYSTEM_PROMPT`:

```python
REVISION_PLANNER_SYSTEM_PROMPT = """
You are revising an existing product intro plan based on new user feedback.
Return a RevisionPlanningResult only.
Do not add or remove scenes.
Do not change scene ids.
Do not change scene durations.
Do not change execution targetDuration.
If explicit scene keyword overrides are provided, treat them as hard constraints.
Only patch fields that should change after the revision.
Keep searchQuery concise and non-empty for every patched scene.
Keep keywords concise and non-empty for every patched scene.
""".strip()
```

3. Add these helpers inside `LangChainPlannerRuntime`:

```python
    def _revision_runnable(self):
        return self.llm.with_structured_output(RevisionPlanningResult)

    def _build_revision_messages(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ):
        return [
            SystemMessage(content=REVISION_PLANNER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    "Current AgentPlan:\n"
                    f"{current_agent.model_dump_json(indent=2)}\n\n"
                    "Current ExecutionPlan:\n"
                    f"{current_execution.model_dump_json(indent=2)}\n\n"
                    "Revision feedback:\n"
                    f"{revision_feedback.model_dump_json(indent=2)}"
                )
            ),
        ]
```

- [ ] **Step 4: Implement revision normalization, validation, merge, and fallback**

Update `backend/services/planner_runtime_langchain.py` by replacing the current `replan_after_user_revision(...)` delegate with:

```python
    def replan_after_user_revision(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        try:
            result = self._revision_runnable().invoke(
                self._build_revision_messages(
                    current_agent=current_agent,
                    current_execution=current_execution,
                    revision_feedback=revision_feedback,
                )
            )
            normalized = self._normalize_revision_result(result)
            next_agent, next_execution, change_summary = self._apply_revision_result(
                current_agent=current_agent,
                current_execution=current_execution,
                revision_feedback=revision_feedback,
                result=normalized,
            )
            return next_agent, next_execution, change_summary
        except Exception:
            return self.deterministic_delegate.replan_after_user_revision(
                current_agent=current_agent,
                current_execution=current_execution,
                revision_feedback=revision_feedback,
            )
```

Then add these helper methods:

```python
    def _normalize_revision_result(
        self,
        result: RevisionPlanningResult,
    ) -> RevisionPlanningResult:
        return RevisionPlanningResult(
            summary=result.summary.strip(),
            audience=result.audience.strip(),
            styleHint=result.styleHint.strip(),
            style=result.style.strip(),
            openIssues=result.openIssues,
            changeSummary=result.changeSummary.strip(),
            scenePatches=[
                {
                    "id": patch.id,
                    "description": patch.description.strip(),
                    "keywords": [keyword.strip() for keyword in patch.keywords if keyword.strip()],
                    "searchQuery": " ".join(patch.searchQuery.split()),
                }
                for patch in result.scenePatches
            ],
        )

    def _apply_revision_result(
        self,
        *,
        current_agent: AgentPlan,
        current_execution: ExecutionPlan,
        revision_feedback: UserRevisionFeedback,
        result: RevisionPlanningResult,
    ) -> tuple[AgentPlan, ExecutionPlan, str]:
        agent_scene_lookup = {scene.id: scene for scene in current_agent.scenes}
        execution_scene_lookup = {scene.id: scene for scene in current_execution.scenes}
        patch_lookup = {}

        for patch in result.scenePatches:
            if patch.id not in agent_scene_lookup or patch.id not in execution_scene_lookup:
                raise ValueError(f"Unknown revision patch scene id: {patch.id}")
            patch_lookup[patch.id] = patch

        updated_agent_scenes = []
        updated_execution_scenes = []
        for agent_scene, execution_scene in zip(current_agent.scenes, current_execution.scenes):
            patch = patch_lookup.get(agent_scene.id)
            override_keywords = revision_feedback.sceneKeywordUpdates.get(agent_scene.id)
            if patch is None:
                updated_agent_scenes.append(agent_scene.model_copy(deep=True))
                updated_execution_scenes.append(execution_scene.model_copy(deep=True))
                continue

            next_keywords = patch.keywords
            next_search_query = patch.searchQuery
            if override_keywords:
                next_keywords = override_keywords
                next_search_query = " ".join(override_keywords)

            if not next_keywords:
                raise ValueError(f"Revision patch keywords are required for scene {patch.id}")
            if not next_search_query:
                raise ValueError(f"Revision patch searchQuery is required for scene {patch.id}")

            next_description = patch.description or agent_scene.description
            updated_agent_scenes.append(
                agent_scene.model_copy(
                    update={
                        "description": next_description,
                        "keywords": next_keywords,
                    }
                )
            )
            updated_execution_scenes.append(
                execution_scene.model_copy(
                    update={
                        "description": patch.description or execution_scene.description,
                        "keywords": next_keywords,
                        "searchQuery": next_search_query,
                    }
                )
            )

        next_agent = current_agent.model_copy(
            update={
                "summary": result.summary or current_agent.summary,
                "understanding": current_agent.understanding.model_copy(
                    update={
                        "audience": result.audience or current_agent.understanding.audience,
                        "styleHint": result.styleHint or current_agent.understanding.styleHint,
                    }
                ),
                "openIssues": result.openIssues or current_agent.openIssues,
                "scenes": updated_agent_scenes,
                "replanHistory": [
                    *current_agent.replanHistory,
                    {
                        "triggerType": "user_revision",
                        "summary": result.changeSummary,
                        "message": revision_feedback.message.strip(),
                        "runtime": "langchain",
                    },
                ],
            }
        )
        next_execution = current_execution.model_copy(
            update={
                "style": result.style or current_execution.style,
                "scenes": updated_execution_scenes,
            }
        )

        if [scene.id for scene in next_agent.scenes] != [scene.id for scene in current_agent.scenes]:
            raise ValueError("agent scene ids changed during revision merge")
        if [scene.id for scene in next_execution.scenes] != [scene.id for scene in current_execution.scenes]:
            raise ValueError("execution scene ids changed during revision merge")
        if any(scene.duration <= 0 for scene in next_agent.scenes):
            raise ValueError("agent scene duration must stay positive")
        if any(scene.duration <= 0 for scene in next_execution.scenes):
            raise ValueError("execution scene duration must stay positive")
        if next_execution.targetDuration != current_execution.targetDuration:
            raise ValueError("execution targetDuration cannot change during revision merge")

        return next_agent, next_execution, result.changeSummary
```

- [ ] **Step 5: Run the focused LangChain revision runtime tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_replans_after_user_revision_with_patch_merge tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_preserves_explicit_scene_keyword_updates_over_model_patch tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_falls_back_to_deterministic_revision_when_patch_targets_unknown_scene tests.test_planner_runtime.PlannerRuntimeTests.test_langchain_runtime_falls_back_to_deterministic_revision_when_model_raises -v
```

Expected: PASS

- [ ] **Step 6: Run the full planner runtime suite**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_runtime -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/planner_runtime_langchain.py tests/test_planner_runtime.py
git commit -m "feat: add langchain user revision replanning"
```

### Task 3: Persist revision runtime trace and tighten integration coverage

**Files:**
- Modify: `backend/services/planner_orchestrator.py`
- Modify: `tests/test_planner_graph.py`
- Modify: `tests/test_agent_planner_phase3.py`
- Modify: `tests/test_agent_persistence.py`

- [ ] **Step 1: Add the failing trace and persistence tests**

Update `tests/test_planner_graph.py` by adding this test to `PlannerGraphTests`:

```python
    def test_run_user_revision_replan_uses_runtime_result_shape_without_changing_trigger(self):
        from backend.services.planner_graph import run_user_revision_replan

        fake_runtime = Mock()
        fake_runtime.replan_after_user_revision.return_value = (
            Mock(model_dump=Mock(return_value={"title": "Agent"})),
            Mock(model_dump=Mock(return_value={"title": "Execution"})),
            "已根据最新修改意见完成计划重写",
        )

        with patch(
            "backend.services.planner_graph.get_planner_runtime",
            return_value=fake_runtime,
        ):
            state = run_user_revision_replan(
                session_id="session-1",
                current_agent_plan={"title": "Agent", "goal": "g", "summary": "s", "scenes": []},
                current_execution_plan={"title": "Execution", "targetDuration": 30, "style": "快节奏社媒短片", "scenes": []},
                revision_feedback={
                    "message": "更商务一点",
                    "sceneKeywordUpdates": {},
                    "revisionSource": "user_message",
                },
            )

        self.assertEqual(state["status"], "replanning_complete")
        self.assertEqual(state["triggerType"], "user_revision")
        self.assertEqual(state["changeSummary"], "已根据最新修改意见完成计划重写")
```

Update `tests/test_agent_planner_phase3.py` by extending `test_post_plan_user_revision_persists_observation_and_plan_vnext` with:

```python
            self.assertIn("revisionRuntime", session_record.planner_trace_json)
            self.assertFalse(session_record.planner_trace_json.get("fallbackUsed", False))
            self.assertEqual(session_record.planner_trace_json["revisionRuntime"], "langchain")
            self.assertEqual(latest.execution_plan_json["style"], "商务演示风格")
            self.assertEqual(latest.execution_plan_json["scenes"][0]["searchQuery"], "城市 车流 黄昏")
```

Add this new test to `tests/test_agent_persistence.py` inside `SessionServiceBehaviorTests`:

```python
    def test_add_user_message_after_plan_persists_revision_plan_when_langchain_revision_falls_back(self):
        from unittest.mock import patch

        from backend.db.repositories import AgentPlanRepository, AgentSessionRepository
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")

        with patch(
            "backend.services.planner_runtime_langchain.LangChainPlannerRuntime._revision_runnable",
            side_effect=RuntimeError("revision runnable unavailable"),
        ):
            updated = service.add_user_message(session.id, "整体再商务一点，目标受众改成销售团队")

        self.assertEqual(updated.plan.style, "商务演示风格")

        db = self.SessionLocal()
        try:
            plan_repo = AgentPlanRepository(db)
            session_repo = AgentSessionRepository(db)
            plans = plan_repo.list_for_session(session.id)
            session_record = session_repo.get(session.id)

            self.assertEqual(plans[-1].version, 2)
            self.assertEqual(plans[-1].trigger_type, "user_revision")
            self.assertEqual(session_record.current_plan_id, plans[-1].id)
            self.assertTrue(session_record.planner_trace_json["fallbackUsed"])
            self.assertEqual(session_record.planner_trace_json["revisionRuntime"], "deterministic_fallback")
        finally:
            db.close()
```

- [ ] **Step 2: Run the focused trace and persistence tests and verify they fail**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph.PlannerGraphTests.test_run_user_revision_replan_uses_runtime_result_shape_without_changing_trigger tests.test_agent_planner_phase3.AgentPlannerPhase3Tests.test_post_plan_user_revision_persists_observation_and_plan_vnext tests.test_agent_persistence.SessionServiceBehaviorTests.test_add_user_message_after_plan_persists_revision_plan_when_langchain_revision_falls_back -v
```

Expected: FAIL because `planner_trace_json` does not yet record revision runtime source or fallback usage.

- [ ] **Step 3: Update revision trace persistence in the orchestrator**

Modify `backend/services/planner_orchestrator.py` inside `persist_user_revision_replan(...)`.

Replace the current state invocation / trace write block with:

```python
        fallback_used = False
        fallback_reason = ""
        try:
            state = run_user_revision_replan(
                session_id=session_record.id,
                current_agent_plan=latest_plan.plan_json,
                current_execution_plan=latest_plan.execution_plan_json,
                revision_feedback={
                    "message": message_record.content,
                    "sceneKeywordUpdates": scene_keyword_updates,
                    "revisionSource": "user_message",
                },
            )
            latest_history = (state.get("agentPlan", {}) or {}).get("replanHistory", [])
            revision_runtime = "langchain"
            if latest_history and latest_history[-1].get("runtime") == "deterministic_fallback":
                revision_runtime = "deterministic_fallback"
                fallback_used = True
                fallback_reason = latest_history[-1].get("fallbackReason", "")
        except Exception:
            raise
```

Then replace the trace write with:

```python
        session_record.current_plan_id = next_plan.id
        session_record.planner_trace_json = {
            **(session_record.planner_trace_json or {}),
            "lastPlanningState": state["status"],
            "triggerType": state["triggerType"],
            "revisionRuntime": revision_runtime,
            "fallbackUsed": fallback_used,
            **({"fallbackReason": fallback_reason} if fallback_reason else {}),
        }
```

Do not remove any existing generic trace fields from other orchestrator methods.

- [ ] **Step 4: Enrich the runtime fallback history entry**

Update the fallback branch in `backend/services/planner_runtime_langchain.py` so it preserves deterministic behavior while marking the returned agent plan history for trace inference:

```python
        except Exception as exc:
            fallback_agent, fallback_execution, fallback_summary = (
                self.deterministic_delegate.replan_after_user_revision(
                    current_agent=current_agent,
                    current_execution=current_execution,
                    revision_feedback=revision_feedback,
                )
            )
            latest_history = fallback_agent.replanHistory[-1] if fallback_agent.replanHistory else None
            if latest_history is not None and latest_history.get("triggerType") == "user_revision":
                latest_history["runtime"] = "deterministic_fallback"
                latest_history["fallbackReason"] = str(exc)
            return fallback_agent, fallback_execution, fallback_summary
```

This keeps graph/orchestrator contracts unchanged while giving the orchestrator a stable signal to persist.

- [ ] **Step 5: Run the focused trace and persistence tests and verify they pass**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_graph.PlannerGraphTests.test_run_user_revision_replan_uses_runtime_result_shape_without_changing_trigger tests.test_agent_planner_phase3.AgentPlannerPhase3Tests.test_post_plan_user_revision_persists_observation_and_plan_vnext tests.test_agent_persistence.SessionServiceBehaviorTests.test_add_user_message_after_plan_persists_revision_plan_when_langchain_revision_falls_back -v
```

Expected: PASS

- [ ] **Step 6: Run the broader regression suites**

Run:

```bash
/Users/linkwind/Code/ClipForge_v2/.venv/bin/python -m unittest tests.test_planner_models tests.test_planner_runtime tests.test_planner_graph tests.test_agent_planner_phase3 tests.test_agent_persistence tests.test_agent_backend tests.test_agent_api_p0 -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/services/planner_orchestrator.py backend/services/planner_runtime_langchain.py tests/test_planner_graph.py tests/test_agent_planner_phase3.py tests/test_agent_persistence.py
git commit -m "feat: persist revision runtime trace"
```

## Plan Self-Review

- Spec coverage check:
  - Revision patch contract: Task 1
  - LangChain conservative merge: Task 2
  - explicit `sceneKeywordUpdates` hard constraint: Task 2
  - deterministic fallback: Tasks 2 and 3
  - planner trace persistence: Task 3
  - no API/UI contract expansion: preserved by scope guardrails and regression suites
- Placeholder scan:
  - No `TODO`, `TBD`, or “similar to” placeholders remain.
- Type consistency:
  - `RevisionScenePatch`, `RevisionPlanningResult`, `UserRevisionFeedback`, `replan_after_user_revision(...)`, `planner_trace_json["revisionRuntime"]`, and `planner_trace_json["fallbackUsed"]` are named consistently across tasks.
