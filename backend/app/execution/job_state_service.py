from datetime import datetime

from backend.db.repositories import AgentJobRepository, AgentSessionRepository


MAX_CURRENT_STEP_LENGTH = 128
FAILED_STEP_PREFIX = "处理失败："


def _format_failed_current_step(message: str) -> str:
    current_step = f"{FAILED_STEP_PREFIX}{message}"
    if len(current_step) <= MAX_CURRENT_STEP_LENGTH:
        return current_step

    ellipsis = "..."
    available_length = MAX_CURRENT_STEP_LENGTH - len(FAILED_STEP_PREFIX) - len(ellipsis)
    if available_length <= 0:
        return FAILED_STEP_PREFIX[:MAX_CURRENT_STEP_LENGTH]
    return f"{FAILED_STEP_PREFIX}{message[:available_length]}{ellipsis}"


class JobStateService:
    def __init__(self, db_session):
        self.job_repo = AgentJobRepository(db_session)
        self.session_repo = AgentSessionRepository(db_session)

    def mark_job_running(self, session_id: str, job_id: str):
        self.job_repo.update_status(
            job_id,
            status="running",
            progress=35,
            current_step="正在搜索素材",
            started_at=datetime.utcnow(),
            error_message=None,
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "searching"
        session_record.progress = 35
        session_record.current_step = "正在搜索素材"
        session_record.error_message = None
        session_record.error_retryable_step = None

    def mark_clips_ready(self, session_id: str, job_id: str, clip_count: int | None = None):
        self.job_repo.update_status(
            job_id,
            progress=60,
            current_step="素材已下载，准备渲染",
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "downloading"
        session_record.progress = 60
        session_record.current_step = "素材已下载，准备渲染"

    def mark_render_started(self, session_id: str, job_id: str):
        self.job_repo.update_status(
            job_id,
            progress=80,
            current_step="正在合成视频",
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "rendering"
        session_record.progress = 80
        session_record.current_step = "正在合成视频"

    def mark_job_succeeded(self, session_id: str, job_id: str, video_url: str):
        self.job_repo.update_status(
            job_id,
            status="succeeded",
            progress=100,
            current_step="完成",
            finished_at=datetime.utcnow(),
            error_message=None,
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "done"
        session_record.progress = 100
        session_record.current_step = "完成"
        session_record.video_url = video_url
        session_record.error_message = None
        session_record.error_retryable_step = None
        self.session_repo.finish_operation(session_id, "job", job_id)

    def mark_job_failed(self, session_id: str, job_id: str, message: str, retryable_step: str):
        current_step = _format_failed_current_step(message)
        self.job_repo.update_status(
            job_id,
            status="failed",
            current_step=current_step,
            finished_at=datetime.utcnow(),
            error_message=message,
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "failed"
        session_record.current_step = current_step
        session_record.error_message = message
        session_record.error_retryable_step = retryable_step
        self.session_repo.fail_operation(session_id, "job", job_id, message)

    def mark_job_requeued_after_replan(
        self,
        session_id: str,
        failed_job_id: str,
        replacement_job_id: str,
    ):
        if not self.session_repo.try_start_operation(session_id, "job", replacement_job_id):
            raise RuntimeError("Session has an active operation")
        session_record = self.session_repo.get(session_id)
        session_record.status = "queued"
        session_record.progress = 25
        session_record.current_step = "任务已重新规划并重新入队"
        session_record.active_job_id = replacement_job_id
        session_record.error_message = None
        session_record.error_retryable_step = None
