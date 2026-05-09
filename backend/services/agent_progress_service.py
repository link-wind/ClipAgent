from datetime import datetime

from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentJobRepository,
    AgentSessionRepository,
)

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


class AgentProgressService:
    def __init__(self, db_session):
        self.db = db_session
        self.session_repo = AgentSessionRepository(db_session)
        self.job_repo = AgentJobRepository(db_session)
        self.event_repo = AgentEventRepository(db_session)
        self.artifact_repo = AgentArtifactRepository(db_session)

    def record_event(
        self,
        session_id: str,
        job_id: str,
        event_type: str,
        step: str,
        message: str,
        progress: float | None = None,
        payload: dict | None = None,
    ):
        # 记录执行事件
        return self.event_repo.create(
            session_id=session_id,
            job_id=job_id,
            event_type=event_type,
            step=step,
            progress=progress,
            message=message,
            payload_json=payload or None,
        )

    def mark_job_running(self, session_id: str, job_id: str):
        # 标记任务开始执行
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
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_started",
            step="searching",
            message="任务开始执行",
            progress=35,
        )

    def mark_clips_ready(self, session_id: str, job_id: str, clip_count: int):
        # 标记素材就绪
        self.job_repo.update_status(
            job_id,
            progress=60,
            current_step="素材已下载，准备渲染",
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "downloading"
        session_record.progress = 60
        session_record.current_step = "素材已下载，准备渲染"
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="clips_ready",
            step="downloading",
            message=f"素材已准备完成，共 {clip_count} 段",
            progress=60,
            payload={"clipCount": clip_count},
        )

    def mark_render_started(self, session_id: str, job_id: str):
        # 标记开始渲染
        self.job_repo.update_status(
            job_id,
            progress=80,
            current_step="正在合成视频",
        )
        session_record = self.session_repo.get(session_id)
        session_record.status = "rendering"
        session_record.progress = 80
        session_record.current_step = "正在合成视频"
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="render_started",
            step="rendering",
            message="开始合成视频",
            progress=80,
        )

    def create_artifact(
        self,
        session_id: str,
        job_id: str,
        artifact_type: str,
        public_url: str,
        local_path: str | None = None,
        scene_id: str | None = None,
        source_url: str | None = None,
        duration: float | None = None,
        metadata: dict | None = None,
    ):
        # 创建产物记录
        return self.artifact_repo.create(
            session_id=session_id,
            job_id=job_id,
            artifact_type=artifact_type,
            scene_id=scene_id,
            source_url=source_url,
            local_path=local_path,
            public_url=public_url,
            duration=duration,
            metadata_json=metadata or None,
        )

    def mark_job_succeeded(self, session_id: str, job_id: str, video_url: str):
        # 标记任务成功
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
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_succeeded",
            step="done",
            message="视频已经生成，可以预览或下载。",
            progress=100,
            payload={"videoUrl": video_url},
        )

    def mark_job_failed(self, session_id: str, job_id: str, message: str, retryable_step: str):
        # 标记任务失败
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
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_failed",
            step="failed",
            message=message,
            progress=session_record.progress,
            payload={"retryableStep": retryable_step},
        )

    def mark_job_requeued_after_replan(
        self,
        session_id: str,
        failed_job_id: str,
        replacement_job_id: str,
    ):
        # 标记会话已根据失败反馈重新规划并重新入队
        session_record = self.session_repo.get(session_id)
        session_record.status = "queued"
        session_record.progress = 25
        session_record.current_step = "任务已重新规划并重新入队"
        session_record.active_job_id = replacement_job_id
        session_record.error_message = None
        session_record.error_retryable_step = None
        self.record_event(
            session_id=session_id,
            job_id=replacement_job_id,
            event_type="job_requeued_after_replan",
            step="queued",
            message="执行失败后已自动重规划并重新入队",
            progress=25,
            payload={
                "failedJobId": failed_job_id,
                "replacementJobId": replacement_job_id,
            },
        )
