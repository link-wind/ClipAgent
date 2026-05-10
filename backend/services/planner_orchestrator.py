from datetime import datetime, timezone

from backend.config import get_settings
from backend.db.repositories import AgentObservationRepository, AgentPlanRepository
from backend.services.planner_graph import (
    run_execution_feedback_replan,
    run_grounding_replan,
    run_initial_planning,
    run_user_revision_replan,
)


class PlannerOrchestrator:
    def persist_initial_plan(self, db, session_record, message_record):
        state = run_initial_planning(session_record.id, message_record.content)
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

    def persist_grounding_replan(self, db, session_record, candidate_ids: list[str]):
        plan_repo = AgentPlanRepository(db)
        observation_repo = AgentObservationRepository(db)
        settings = get_settings()

        latest_plan = plan_repo.get_latest_for_session(session_record.id)
        if latest_plan is None:
            raise RuntimeError("Grounding replan requires an existing plan version")

        grounding_summary = session_record.grounding_summary_json or {}
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

    def persist_user_revision_replan(self, db, session_record, message_record, scene_keyword_updates: dict[int, list[str]]):
        plan_repo = AgentPlanRepository(db)
        observation_repo = AgentObservationRepository(db)
        settings = get_settings()

        latest_plan = plan_repo.get_latest_for_session(session_record.id)
        if latest_plan is None:
            raise RuntimeError("User revision replan requires an existing plan version")

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
        session_record.planner_trace_json = {
            **(session_record.planner_trace_json or {}),
            "lastPlanningState": state["status"],
            "triggerType": state["triggerType"],
            "revisionRuntime": revision_runtime,
            "fallbackUsed": fallback_used,
        }
        if fallback_reason:
            session_record.planner_trace_json["fallbackReason"] = fallback_reason
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
        session_record.planner_trace_json = {
            **planner_trace,
            "lastPlanningState": state["status"],
            "triggerType": state["triggerType"],
            "autoExecutionReplanCount": auto_replan_count + 1,
        }
        return next_plan
