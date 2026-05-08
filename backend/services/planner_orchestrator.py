from datetime import datetime, timezone

from backend.config import get_settings
from backend.db.repositories import AgentObservationRepository, AgentPlanRepository
from backend.services.planner_graph import run_initial_planning


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
