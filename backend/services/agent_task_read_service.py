from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentJobRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.models.agent import (
    AgentDashboardSummary,
    AgentError,
    AgentTaskDetail,
    AgentTaskSummary,
)
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_step_snapshot_service import AgentStepSnapshotService


RUNNING_JOB_STATUSES = {"queued", "pending", "running"}


class AgentTaskReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.read_service = AgentReadService(session_factory=session_factory)
        self.step_snapshot_service = AgentStepSnapshotService()

    def list_tasks(self, limit: int = 50) -> list[AgentTaskSummary]:
        # 读取最近任务摘要
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            event_repo = AgentEventRepository(db)
            jobs = AgentJobRepository(db).list_recent(limit=limit)
            session_by_id = self._load_sessions_for_jobs(session_repo, jobs)
            return [
                self._build_task_summary(
                    job,
                    session_by_id.get(job.session_id),
                    self._resolve_retryable_step(event_repo.list_for_job(job.id)),
                )
                for job in jobs
            ]

    def read_task(self, job_id: str) -> AgentTaskDetail:
        # 读取任务详情
        with self.session_factory() as db:
            job = AgentJobRepository(db).get(job_id)
            if job is None:
                raise KeyError(job_id)

            session = AgentSessionRepository(db).get(job.session_id) if job.session_id else None
            plan = AgentPlanRepository(db).get(job.plan_id) if job.plan_id else None
            artifacts = AgentArtifactRepository(db).list_for_job(job.id)
            events = AgentEventRepository(db).list_for_job(job.id)
            clip_rows = [row for row in artifacts if row.artifact_type == "clip"]
            video_url = self._resolve_video_url(artifacts, events)
            retryable_step = self._resolve_retryable_step(events)
            summary = self._build_task_summary(job, session, retryable_step)
            return AgentTaskDetail(
                **summary.model_dump(),
                events=self.read_service.build_event_response(events),
                clips=[self.read_service._build_clip_info(row) for row in clip_rows],
                steps=self.step_snapshot_service.build_task_steps(
                    session_record=session,
                    job_record=job,
                    plan_row=plan,
                    artifact_rows=artifacts,
                    event_rows=events,
                ),
                error=(
                    AgentError(
                        message=job.error_message,
                        retryableStep=retryable_step,
                    )
                    if job.error_message
                    else None
                ),
                videoUrl=video_url,
            )

    def read_dashboard(self) -> AgentDashboardSummary:
        # 汇总仪表盘计数和最近任务
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)
            jobs = job_repo.list_recent(limit=50)
            session_by_id = self._load_sessions_for_jobs(session_repo, jobs)
            return AgentDashboardSummary(
                totalSessions=session_repo.count_all(),
                activeTasks=job_repo.count_by_statuses(RUNNING_JOB_STATUSES),
                completedTasks=job_repo.count_by_status("succeeded"),
                failedTasks=job_repo.count_by_status("failed"),
                recentTasks=[
                    self._build_task_summary(
                        job,
                        session_by_id.get(job.session_id),
                        self._resolve_retryable_step(event_repo.list_for_job(job.id)),
                    )
                    for job in jobs
                ],
            )

    def _build_task_summary(self, job, session, retryable_step: str | None = None) -> AgentTaskSummary:
        title = session.title if session and session.title else "未命名视频任务"
        return AgentTaskSummary(
            id=job.id,
            sessionId=job.session_id or "",
            title=title,
            status=job.status,
            progress=job.progress,
            currentStep=job.current_step or "",
            currentStepId=self._resolve_summary_current_step_id(job, retryable_step),
            createdAt=job.created_at.isoformat(),
            updatedAt=job.updated_at.isoformat(),
        )

    def _load_sessions_for_jobs(self, session_repo, jobs) -> dict[str, object]:
        session_ids = [job.session_id for job in jobs if job.session_id]
        return {session.id: session for session in session_repo.get_many(session_ids)}

    def _resolve_video_url(self, artifacts, events) -> str | None:
        for row in reversed(artifacts):
            if row.artifact_type == "video" and row.public_url:
                return row.public_url

        for row in reversed(events):
            payload = row.payload_json or {}
            video_url = payload.get("videoUrl")
            if video_url:
                return str(video_url)

        return None

    def _resolve_retryable_step(self, events) -> str | None:
        for row in reversed(events):
            payload = row.payload_json or {}
            retryable_step = payload.get("retryableStep")
            if retryable_step:
                return str(retryable_step)

        return None

    def _resolve_summary_current_step_id(self, job, retryable_step: str | None = None):
        if job.status == "failed" and retryable_step:
            normalized_step = self.step_snapshot_service.normalize_retryable_step(retryable_step)
            if normalized_step:
                return normalized_step

        return self.step_snapshot_service.resolve_current_step_id(
            job.status,
            job.current_step or "",
        )
