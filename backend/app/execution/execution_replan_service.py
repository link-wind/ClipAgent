from backend.db.repositories import AgentJobRepository, AgentSessionRepository
from backend.app.planning.orchestrator import PlannerOrchestrator


def should_attempt_execution_replan(retryable_step: str) -> bool:
    return retryable_step == "searching"


def extract_failed_scene_ids(exc: Exception) -> list[int]:
    failed_scene_ids = getattr(exc, "failed_scene_ids", None)
    if not isinstance(failed_scene_ids, list):
        return []

    normalized_scene_ids: list[int] = []
    for scene_id in failed_scene_ids:
        if isinstance(scene_id, int) and not isinstance(scene_id, bool) and scene_id not in normalized_scene_ids:
            normalized_scene_ids.append(scene_id)
    return normalized_scene_ids


def build_execution_feedback_payload(exc: Exception) -> dict[str, object]:
    payload: dict[str, object] = {
        "failedSceneIds": extract_failed_scene_ids(exc),
        "failureReason": str(exc),
        "retryable": True,
        "feedbackSource": "worker_failure",
    }

    failure_category = getattr(exc, "failure_category", None)
    if isinstance(failure_category, str) and failure_category:
        payload["failureCategory"] = failure_category

    primary_provider = getattr(exc, "primary_provider", None)
    if isinstance(primary_provider, str) and primary_provider:
        payload["primaryProvider"] = primary_provider

    provider_diagnostics = getattr(exc, "provider_diagnostics", None)
    if isinstance(provider_diagnostics, list) and provider_diagnostics:
        payload["providerDiagnostics"] = list(provider_diagnostics)

    scene_diagnostics = getattr(exc, "scene_diagnostics", None)
    if isinstance(scene_diagnostics, list) and scene_diagnostics:
        payload["sceneDiagnostics"] = list(scene_diagnostics)

    retry_strategy_hint = getattr(exc, "retry_strategy_hint", None)
    if isinstance(retry_strategy_hint, str) and retry_strategy_hint:
        payload["retryStrategyHint"] = retry_strategy_hint

    return payload


def build_worker_failure_payload(exc: Exception, retryable_step: str) -> dict[str, object]:
    payload = build_execution_feedback_payload(exc)
    payload["retryableStep"] = retryable_step
    return payload


class ExecutionReplanService:
    def __init__(self, planner_orchestrator: PlannerOrchestrator | None = None):
        self.planner_orchestrator = planner_orchestrator or PlannerOrchestrator()

    def attempt_replan(self, *, db, progress_service, job_record, exc: Exception, retryable_step: str) -> str | None:
        if not should_attempt_execution_replan(retryable_step):
            return None

        session_record = AgentSessionRepository(db).get(job_record.session_id)
        if session_record is None:
            return None

        next_plan = self.planner_orchestrator.persist_execution_feedback_replan(
            db=db,
            session_record=session_record,
            failed_job_record=job_record,
            execution_feedback=build_execution_feedback_payload(exc),
        )
        replacement_job = AgentJobRepository(db).create(
            session_id=job_record.session_id,
            plan_id=next_plan.id,
            job_type=job_record.job_type,
            status="queued",
            progress=0,
            current_step="任务已重新入队",
            max_attempts=job_record.max_attempts,
        )
        progress_service.mark_job_requeued_after_replan(
            session_id=job_record.session_id,
            failed_job_id=job_record.id,
            replacement_job_id=replacement_job.id,
        )
        return replacement_job.id
