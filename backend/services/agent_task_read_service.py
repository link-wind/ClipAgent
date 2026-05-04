from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentJobRepository,
    AgentSessionRepository,
)
from backend.models.agent import AgentDashboardSummary, AgentError, AgentTaskDetail, AgentTaskSummary
from backend.services.agent_read_service import AgentReadService


RUNNING_JOB_STATUSES = {"queued", "searching", "downloading", "rendering", "pending"}


class AgentTaskReadService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.read_service = AgentReadService(session_factory=session_factory)

    def list_tasks(self, limit: int = 50) -> list[AgentTaskSummary]:
        # 读取最近任务摘要
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            return [
                self._build_task_summary(job, session_repo.get(job.session_id) if job.session_id else None)
                for job in AgentJobRepository(db).list_recent(limit=limit)
            ]

    def read_task(self, job_id: str) -> AgentTaskDetail:
        # 读取任务详情
        with self.session_factory() as db:
            job = AgentJobRepository(db).get(job_id)
            if job is None:
                raise KeyError(job_id)

            session = AgentSessionRepository(db).get(job.session_id) if job.session_id else None
            artifacts = AgentArtifactRepository(db).list_for_session(job.session_id) if job.session_id else []
            events = AgentEventRepository(db).list_for_session(job.session_id) if job.session_id else []
            clip_rows = [row for row in artifacts if row.artifact_type == "clip"]
            summary = self._build_task_summary(job, session)
            return AgentTaskDetail(
                **summary.model_dump(),
                events=self.read_service.build_event_response(
                    row for row in events if row.job_id == job.id
                ),
                clips=[
                    self.read_service._build_clip_info(row)
                    for row in clip_rows
                    if row.job_id == job.id
                ],
                error=(
                    AgentError(
                        message=job.error_message,
                        retryableStep=session.error_retryable_step if session else None,
                    )
                    if job.error_message
                    else None
                ),
                videoUrl=session.video_url if session else None,
            )

    def read_dashboard(self) -> AgentDashboardSummary:
        # 汇总仪表盘计数和最近任务
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            jobs = AgentJobRepository(db).list_recent(limit=50)
            recent_sessions = session_repo.list_recent(limit=20)
            session_by_id = {session.id: session for session in recent_sessions}
            return AgentDashboardSummary(
                totalSessions=len(recent_sessions),
                activeTasks=sum(1 for job in jobs if job.status in RUNNING_JOB_STATUSES),
                completedTasks=sum(1 for job in jobs if job.status == "done"),
                failedTasks=sum(1 for job in jobs if job.status == "failed"),
                recentTasks=[
                    self._build_task_summary(
                        job,
                        session_by_id.get(job.session_id)
                        or (session_repo.get(job.session_id) if job.session_id else None),
                    )
                    for job in jobs
                ],
            )

    def _build_task_summary(self, job, session) -> AgentTaskSummary:
        title = session.title if session and session.title else "未命名视频任务"
        return AgentTaskSummary(
            id=job.id,
            sessionId=job.session_id or "",
            title=title,
            status=job.status,
            progress=job.progress,
            currentStep=job.current_step or "",
            createdAt=job.created_at.isoformat(),
            updatedAt=job.updated_at.isoformat(),
        )
