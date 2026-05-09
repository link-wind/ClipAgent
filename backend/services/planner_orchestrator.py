from datetime import datetime, timezone

from backend.config import get_settings
from backend.db.repositories import AgentObservationRepository, AgentPlanRepository
from backend.services.planner_graph import run_grounding_replan, run_initial_planning


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
