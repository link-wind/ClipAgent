from dataclasses import asdict
from datetime import datetime, timezone

from backend.app.skills.registry import BuiltinSkillRegistry
from backend.config import get_settings
from backend.db.repositories import (
    AgentObservationRepository,
    AgentPlanRepository,
    AgentRunRepository,
    AgentStepRepository,
)
from backend.domain.skills.contracts import PlannerRequest, SkillRunSummary, SkillSelectionRequest
from backend.runtime.context_engine import ContextBundle, ContextEngine, ContextRequest
from backend.runtime.skill_engine import SkillEngine
from backend.runtime.trace_recorder import TraceEvent, TraceRecorder
from backend.app.agent.step_service import AgentStepService
from backend.app.planning.graph import (
    run_execution_feedback_replan,
    run_grounding_replan,
    run_initial_planning,
    run_user_revision_replan,
)


def format_context_for_planner(message: str, context: ContextBundle) -> str:
    if not context.documents:
        return ""

    lines = ["Known context:"]
    for document in context.documents[:3]:
        content = str(document.get("content", "")).strip()
        if content:
            lines.append(f"- {content}")
    return "\n".join(lines).strip()


def _build_user_revision_context_payload(message: str, context: ContextBundle) -> dict:
    planner_context = format_context_for_planner(message, context)
    return {"plannerContext": planner_context} if planner_context else {}


class PlannerOrchestrator:
    def __init__(
        self,
        *,
        skill_engine: SkillEngine | None = None,
        skill_registry: BuiltinSkillRegistry | None = None,
        context_engine: ContextEngine | None = None,
        trace_recorder: TraceRecorder | None = None,
    ) -> None:
        self.skill_engine = skill_engine or SkillEngine()
        self.skill_registry = skill_registry or BuiltinSkillRegistry()
        self.context_engine = context_engine
        self.trace_recorder = trace_recorder

    def persist_initial_plan(self, db, session_record, message_record, run_id: str | None = None):
        context = self._build_context(
            db=db,
            session_record=session_record,
            message_record=message_record,
            run_id=run_id,
            scope="planning",
        )
        planner_context = format_context_for_planner(message_record.content, context)
        self._record_skill_observability(
            db=db,
            session_record=session_record,
            run_id=run_id,
            run_type="initial_planning",
            user_message=message_record.content,
            context={"plannerContext": planner_context} if planner_context else {},
        )
        state = run_initial_planning(
            session_record.id,
            message_record.content,
            context_text=planner_context,
        )
        observation_repo = AgentObservationRepository(db)
        plan_repo = AgentPlanRepository(db)
        settings = get_settings()

        observation_repo.create(
            session_id=session_record.id,
            observation_type="user_message",
            summary="初始 brief",
            payload_json={"message": message_record.content},
            source_message_id=message_record.id,
        )

        plan_record = plan_repo.create(
            session_id=session_record.id,
            version=1,
            parent_plan_id=None,
            trigger_type="initial_brief",
            planner_mode=settings.planner_mode,
            planner_model=settings.planner_model,
            title=state["executionPlan"]["title"],
            target_duration=int(state["executionPlan"]["targetDuration"]),
            style=state["executionPlan"]["style"],
            plan_json=state["agentPlan"],
            execution_plan_json=state["executionPlan"],
            change_summary="根据初始 brief 生成第一版计划",
            status="ready",
        )

        session_record.current_plan_id = plan_record.id
        session_record.planner_trace_json = {
            "lastPlanningState": state["status"],
            "plannedAt": datetime.now(timezone.utc).isoformat(),
        }
        return plan_record

    def _build_context(self, db, session_record, message_record, run_id: str | None, scope: str) -> ContextBundle:
        context_engine = self.context_engine or ContextEngine(
            db_session=db,
            trace_recorder=self.trace_recorder or TraceRecorder(db),
        )
        return context_engine.build_context(
            ContextRequest(
                session_id=session_record.id,
                message=message_record.content,
                scope=scope,
                run_id=run_id,
            )
        )

    def persist_grounding_replan(self, db, session_record, candidate_ids: list[str], run_id: str | None = None):
        plan_repo = AgentPlanRepository(db)
        observation_repo = AgentObservationRepository(db)
        settings = get_settings()

        latest_plan = plan_repo.get_latest_for_session(session_record.id)
        if latest_plan is None:
            raise RuntimeError("Grounding replan requires an existing plan version")

        grounding_summary = session_record.grounding_summary_json or {}
        self._record_skill_observability(
            db=db,
            session_record=session_record,
            run_id=run_id,
            run_type="grounding_replan",
            user_message=session_record.title or "确认候选产品画面",
            context={
                "selectedCandidateIds": candidate_ids,
                "groundingStatus": session_record.grounding_status or "",
                "productName": grounding_summary.get("productName", ""),
                "featureHints": grounding_summary.get("featureHints", []) or [],
            },
        )
        state = run_grounding_replan(
            session_id=session_record.id,
            current_agent_plan=latest_plan.plan_json,
            current_execution_plan=latest_plan.execution_plan_json,
            grounding_feedback={
                **grounding_summary,
                "selectedCandidateIds": candidate_ids,
            },
            confirmation_feedback={
                "selectedCandidateIds": candidate_ids,
                "confirmationSource": "user_select",
            },
        )

        observation_repo.create(
            session_id=session_record.id,
            plan_id=latest_plan.id,
            observation_type="grounding_confirmation",
            summary="用户确认候选产品画面并触发重规划",
            payload_json={"selectedCandidateIds": candidate_ids},
        )

        next_plan = plan_repo.create(
            session_id=session_record.id,
            version=latest_plan.version + 1,
            parent_plan_id=latest_plan.id,
            trigger_type="grounding_confirmation",
            planner_mode=settings.planner_mode,
            planner_model=settings.planner_model,
            title=state["executionPlan"]["title"],
            target_duration=int(state["executionPlan"]["targetDuration"]),
            style=state["executionPlan"]["style"],
            plan_json=state["agentPlan"],
            execution_plan_json=state["executionPlan"],
            change_summary=state["changeSummary"],
            status="ready",
        )
        session_record.current_plan_id = next_plan.id
        session_record.planner_trace_json = {
            "lastPlanningState": state["status"],
            "triggerType": state["triggerType"],
        }
        return next_plan

    def persist_user_revision_replan(
        self,
        db,
        session_record,
        message_record,
        scene_keyword_updates: dict[int, list[str]],
        run_id: str | None = None,
    ):
        plan_repo = AgentPlanRepository(db)
        observation_repo = AgentObservationRepository(db)
        settings = get_settings()

        latest_plan = plan_repo.get_latest_for_session(session_record.id)
        if latest_plan is None:
            raise RuntimeError("User revision replan requires an existing plan version")

        context = self._build_context(
            db=db,
            session_record=session_record,
            message_record=message_record,
            run_id=run_id,
            scope="user_revision",
        )
        context_payload = _build_user_revision_context_payload(message_record.content, context)
        skill_context = {
            **({"sceneKeywordUpdates": scene_keyword_updates} if scene_keyword_updates else {}),
            **context_payload,
        }
        self._record_skill_observability(
            db=db,
            session_record=session_record,
            run_id=run_id,
            run_type="user_revision",
            user_message=message_record.content,
            context=skill_context,
        )
        state = run_user_revision_replan(
            session_id=session_record.id,
            current_agent_plan=latest_plan.plan_json,
            current_execution_plan=latest_plan.execution_plan_json,
            revision_feedback={
                "message": message_record.content,
                "sceneKeywordUpdates": scene_keyword_updates,
                "revisionSource": "user_message",
                **context_payload,
            },
        )

        observation_repo.create(
            session_id=session_record.id,
            plan_id=latest_plan.id,
            observation_type="user_revision",
            summary="用户提交 plan revision 并触发重规划",
            payload_json={
                "message": message_record.content,
                "sceneKeywordUpdates": scene_keyword_updates,
            },
            source_message_id=message_record.id,
        )

        next_plan = plan_repo.create(
            session_id=session_record.id,
            version=latest_plan.version + 1,
            parent_plan_id=latest_plan.id,
            trigger_type="user_revision",
            planner_mode=settings.planner_mode,
            planner_model=settings.planner_model,
            title=state["executionPlan"]["title"],
            target_duration=int(state["executionPlan"]["targetDuration"]),
            style=state["executionPlan"]["style"],
            plan_json=state["agentPlan"],
            execution_plan_json=state["executionPlan"],
            change_summary=state["changeSummary"],
            status="ready",
        )
        latest_history = ((state.get("agentPlan") or {}).get("replanHistory") or [])
        latest_revision_trace = latest_history[-1] if latest_history else {}
        revision_runtime = "langchain"
        fallback_used = False
        fallback_reason = ""
        if latest_revision_trace.get("runtime") == "deterministic_fallback":
            revision_runtime = "deterministic_fallback"
            fallback_used = True
            fallback_reason = latest_revision_trace.get("fallbackReason", "")
        session_record.current_plan_id = next_plan.id
        planner_trace = {
            **(session_record.planner_trace_json or {}),
            "lastPlanningState": state["status"],
            "triggerType": state["triggerType"],
            "revisionRuntime": revision_runtime,
            "fallbackUsed": fallback_used,
        }
        if not fallback_used:
            planner_trace.pop("fallbackReason", None)
        if fallback_reason:
            planner_trace["fallbackReason"] = fallback_reason
        session_record.planner_trace_json = planner_trace
        return next_plan

    def persist_execution_feedback_replan(
        self,
        db,
        session_record,
        failed_job_record,
        execution_feedback: dict,
    ):
        plan_repo = AgentPlanRepository(db)
        observation_repo = AgentObservationRepository(db)
        settings = get_settings()

        latest_plan = plan_repo.get_latest_for_session(session_record.id)
        if latest_plan is None:
            raise RuntimeError("Execution feedback replan requires an existing plan version")

        planner_trace = session_record.planner_trace_json or {}
        auto_replan_count = int(planner_trace.get("autoExecutionReplanCount", 0) or 0)
        if auto_replan_count >= 1:
            raise RuntimeError("Execution feedback replan limit reached")

        self._record_skill_observability(
            db=db,
            session_record=session_record,
            run_id=None,
            run_type="execution_feedback_replan",
            user_message=execution_feedback.get("repairPrompt")
            or execution_feedback.get("message")
            or "执行失败后触发重规划",
            failure_context=execution_feedback,
        )
        state = run_execution_feedback_replan(
            session_id=session_record.id,
            current_agent_plan=latest_plan.plan_json,
            current_execution_plan=latest_plan.execution_plan_json,
            execution_feedback=execution_feedback,
        )

        observation_repo.create(
            session_id=session_record.id,
            plan_id=latest_plan.id,
            observation_type="execution_feedback",
            summary="执行失败反馈触发自动重规划",
            payload_json=execution_feedback,
            source_job_id=failed_job_record.id,
        )

        next_plan = plan_repo.create(
            session_id=session_record.id,
            version=latest_plan.version + 1,
            parent_plan_id=latest_plan.id,
            trigger_type="execution_feedback",
            planner_mode=settings.planner_mode,
            planner_model=settings.planner_model,
            title=state["executionPlan"]["title"],
            target_duration=int(state["executionPlan"]["targetDuration"]),
            style=state["executionPlan"]["style"],
            plan_json=state["agentPlan"],
            execution_plan_json=state["executionPlan"],
            change_summary=state["changeSummary"],
            status="ready",
        )

        session_record.current_plan_id = next_plan.id
        next_trace = {
            **planner_trace,
            "lastPlanningState": state["status"],
            "triggerType": state["triggerType"],
            "autoExecutionReplanCount": auto_replan_count + 1,
        }
        next_trace.pop("revisionRuntime", None)
        next_trace.pop("fallbackUsed", None)
        next_trace.pop("fallbackReason", None)
        session_record.planner_trace_json = next_trace
        return next_plan

    def _record_skill_observability(
        self,
        *,
        db,
        session_record,
        run_id: str | None,
        run_type: str,
        user_message: str,
        context: dict | None = None,
        failure_context: dict | None = None,
    ) -> None:
        context = context or {}
        failure_context = failure_context or {}
        selection_request = SkillSelectionRequest(
            session_id=session_record.id,
            run_id=run_id or "",
            run_type=run_type,
            user_message=user_message,
            context=context,
            failure_context=failure_context,
        )
        run_record = AgentRunRepository(db).get(run_id) if run_id else None
        if run_record is not None:
            self._merge_run_payloads(
                db,
                run_record,
                input_payload={"skillSelectionRequest": self._selection_request_payload(selection_request)},
            )

        trace_recorder = TraceRecorder(db)
        step_service = AgentStepService(db) if run_id else None
        step_repo = AgentStepRepository(db) if run_id else None
        sequence = len(step_repo.list_for_run(run_id)) if step_repo and run_id else 0
        select_step = None
        build_step = None
        build_summary_payload = None
        selection_payload = {}

        try:
            if step_service is not None:
                select_step = step_service.start_step(
                    session_id=session_record.id,
                    run_id=run_id,
                    step_key="select_strategy",
                    title="选择规划策略",
                    description="根据当前 planning 场景选择 skill 与策略。",
                    sequence=sequence + 1,
                )

            selection = self.skill_engine.select_skill(selection_request)
            selection_payload = {
                "skillId": selection.skill_id,
                "skillVersion": selection.version,
                "reason": selection.reason,
                "runType": run_type,
            }
            trace_recorder.record(
                TraceEvent(
                    session_id=session_record.id,
                    run_id=run_id,
                    step_id=select_step.id if select_step is not None else None,
                    event_type="skill_selected",
                    message=selection.reason or selection.skill_id,
                    payload=selection_payload,
                )
            )
            if step_service is not None and select_step is not None:
                step_service.succeed_step(
                    select_step.id,
                    summary=f"已选择 {selection.skill_id}",
                    result=selection_payload,
                )
            if run_record is not None:
                self._merge_run_payloads(
                    db,
                    run_record,
                    metadata_payload={"skill": selection_payload},
                )

            if step_service is not None:
                build_step = step_service.start_step(
                    session_id=session_record.id,
                    run_id=run_id,
                    step_key="build_planner_request",
                    title="构建 Planner Request",
                    description="根据已选 skill 生成最小 Planner Request 证据。",
                    sequence=sequence + 2,
                )

            trace_recorder.record(
                TraceEvent(
                    session_id=session_record.id,
                    run_id=run_id,
                    step_id=build_step.id if build_step is not None else None,
                    event_type="skill_run_started",
                    message=f"Building planner request with {selection.skill_id}",
                    payload=selection_payload,
                )
            )
            build_result = self.skill_engine.build_planner_request(selection_request, selection=selection)
            build_summary_payload = self._skill_run_summary_payload(build_result.summary)
            if build_result.summary.status != "succeeded" or build_result.planner_request is None:
                raise RuntimeError(build_result.summary.error_message or "Skill failed to build planner request")
            planner_request = build_result.planner_request
            planner_request_payload = self._planner_request_payload(planner_request)
            trace_recorder.record(
                TraceEvent(
                    session_id=session_record.id,
                    run_id=run_id,
                    step_id=build_step.id if build_step is not None else None,
                    event_type="skill_run_succeeded",
                    message=f"Planner request ready for {selection.skill_id}",
                    payload={
                        **selection_payload,
                        "skillRunSummary": build_summary_payload,
                        "plannerRequest": planner_request_payload,
                    },
                )
            )
            if step_service is not None and build_step is not None:
                step_service.succeed_step(
                    build_step.id,
                    summary="Planner Request 已构建",
                    result=planner_request_payload,
                )
            if run_record is not None:
                self._merge_run_payloads(
                    db,
                    run_record,
                    output_payload={"plannerRequest": planner_request_payload},
                    metadata_payload={
                        "skill": {
                            **selection_payload,
                            "status": "succeeded",
                        }
                    },
                )
        except Exception as exc:
            failed_step = build_step or select_step
            if step_service is not None and failed_step is not None:
                step_service.fail_step(
                    failed_step.id,
                    message=str(exc),
                    retryable=False,
                )
            trace_recorder.record(
                TraceEvent(
                    session_id=session_record.id,
                    run_id=run_id,
                    step_id=failed_step.id if failed_step is not None else None,
                    event_type="skill_run_failed",
                    level="error",
                    message=str(exc),
                    payload={
                        **selection_payload,
                        "runType": run_type,
                        "message": str(exc),
                        "skillRunSummary": self._skill_run_failed_summary_payload(
                            selection_payload=selection_payload,
                            build_summary_payload=build_summary_payload,
                            error_message=str(exc),
                        ),
                    },
                )
            )
            if run_record is not None:
                self._merge_run_payloads(
                    db,
                    run_record,
                    metadata_payload={
                        "skill": {
                            **(run_record.metadata_json or {}).get("skill", {}),
                            "status": "failed",
                            "errorMessage": str(exc),
                        }
                    },
                )
            raise

    def _merge_run_payloads(
        self,
        db,
        run_record,
        *,
        input_payload: dict | None = None,
        output_payload: dict | None = None,
        metadata_payload: dict | None = None,
    ) -> None:
        if input_payload:
            run_record.input_json = {
                **(run_record.input_json or {}),
                **input_payload,
            }
        if output_payload:
            run_record.output_json = {
                **(run_record.output_json or {}),
                **output_payload,
            }
        if metadata_payload:
            run_record.metadata_json = {
                **(run_record.metadata_json or {}),
                **metadata_payload,
            }
        db.add(run_record)
        db.flush()
        db.refresh(run_record)

    def _selection_request_payload(self, request: SkillSelectionRequest) -> dict:
        payload = asdict(request)
        payload["user_message"] = str(payload.get("user_message", ""))[:120]
        return payload

    def _planner_request_payload(self, planner_request: PlannerRequest) -> dict:
        return {
            "action": planner_request.action,
            "messageCount": len(planner_request.messages),
            "contextItemTypes": [
                item.get("type")
                for item in planner_request.context_items
                if isinstance(item, dict) and item.get("type")
            ],
            "outputSchema": planner_request.output_schema,
            "constraintKeys": sorted(planner_request.constraints.keys()),
            "failureContextKeys": sorted(planner_request.failure_context.keys()),
            "retryStrategyHint": planner_request.retry_strategy_hint,
            "failedSceneIds": planner_request.failed_scene_ids,
        }

    def _skill_run_summary_payload(self, summary: SkillRunSummary) -> dict:
        return {
            "skillId": summary.skill_id,
            "skillVersion": summary.skill_version,
            "status": summary.status,
            "inputSummary": summary.input_summary,
            "outputSummary": summary.output_summary,
            "errorMessage": summary.error_message,
        }

    def _skill_run_failed_summary_payload(
        self,
        *,
        selection_payload: dict,
        build_summary_payload: dict | None,
        error_message: str,
    ) -> dict:
        return {
            "skillId": (build_summary_payload or {}).get("skillId") or selection_payload.get("skillId", ""),
            "skillVersion": (build_summary_payload or {}).get("skillVersion")
            or selection_payload.get("skillVersion", ""),
            "status": "failed",
            "inputSummary": (build_summary_payload or {}).get("inputSummary", ""),
            "outputSummary": (build_summary_payload or {}).get("outputSummary", ""),
            "errorMessage": error_message,
        }
