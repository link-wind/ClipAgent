from backend.app.execution.artifact_service import ExecutionArtifactService
from backend.app.execution.event_service import ExecutionEventService
from backend.app.execution.job_state_service import JobStateService
from backend.app.execution.step_lifecycle import StepLifecycleService


STEP_DEFINITIONS = {
    "search_assets": ("搜索素材", "根据最终方案搜索候选素材并记录搜索结果。", 6),
    "prepare_assets": ("准备素材", "下载、裁剪、整理素材，形成渲染输入。", 7),
    "render_video": ("渲染视频", "调用渲染流程，生成视频产物或失败原因。", 8),
}

RETRYABLE_STEP_TO_STEP_KEY = {
    "searching": "search_assets",
    "downloading": "prepare_assets",
    "rendering": "render_video",
}


class AgentProgressService:
    """Legacy compatibility facade over execution-side services."""

    def __init__(self, db_session):
        self.db = db_session
        self.job_state_service = JobStateService(db_session)
        self.event_service = ExecutionEventService(db_session)
        self.artifact_service = ExecutionArtifactService(db_session)
        self.step_lifecycle = StepLifecycleService(db_session)

        # Keep common attributes alive for compatibility with older tests/callers.
        self.job_repo = self.job_state_service.job_repo
        self.session_repo = self.job_state_service.session_repo
        self.event_repo = self.event_service.event_repo
        self.artifact_repo = self.artifact_service.artifact_repo
        self.step_repo = self.step_lifecycle.step_repo
        self.step_service = self.step_lifecycle.step_service

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
        return self.event_service.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type=event_type,
            step=step,
            message=message,
            progress=progress,
            payload=payload,
        )

    def mark_job_running(self, session_id: str, job_id: str):
        self.job_state_service.mark_job_running(session_id, job_id)
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_started",
            step="searching",
            message="任务开始执行",
            progress=35,
        )
        self._ensure_job_step(session_id, job_id, "search_assets")

    def mark_clips_ready(self, session_id: str, job_id: str, clip_count: int):
        self.job_state_service.mark_clips_ready(session_id, job_id, clip_count)
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="clips_ready",
            step="downloading",
            message=f"素材已准备完成，共 {clip_count} 段",
            progress=60,
            payload={"clipCount": clip_count},
        )
        search_step = self._ensure_job_step(session_id, job_id, "search_assets")
        if search_step.status != "succeeded":
            self.step_service.succeed_step(
                search_step.id,
                summary=f"已找到 {clip_count} 段素材",
                result={"selectedCount": clip_count},
            )
        prepare_step = self._ensure_job_step(session_id, job_id, "prepare_assets")
        self.step_service.succeed_step(
            prepare_step.id,
            summary=f"素材已准备完成，共 {clip_count} 段",
            result={"clipCount": clip_count},
        )

    def mark_render_started(self, session_id: str, job_id: str):
        self.job_state_service.mark_render_started(session_id, job_id)
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="render_started",
            step="rendering",
            message="开始合成视频",
            progress=80,
        )
        self._ensure_job_step(session_id, job_id, "render_video")

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
        return self.artifact_service.create_artifact(
            session_id=session_id,
            job_id=job_id,
            artifact_type=artifact_type,
            public_url=public_url,
            local_path=local_path,
            scene_id=scene_id,
            source_url=source_url,
            duration=duration,
            metadata=metadata,
        )

    def mark_job_succeeded(self, session_id: str, job_id: str, video_url: str):
        self.job_state_service.mark_job_succeeded(session_id, job_id, video_url)
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_succeeded",
            step="done",
            message="视频已经生成，可以预览或下载。",
            progress=100,
            payload={"videoUrl": video_url},
        )
        render_step = self._ensure_job_step(session_id, job_id, "render_video")
        if render_step.status != "succeeded":
            self.step_service.succeed_step(
                render_step.id,
                summary="视频已经生成",
                result={"videoUrl": video_url},
            )

    def mark_job_failed(self, session_id: str, job_id: str, message: str, retryable_step: str):
        self.job_state_service.mark_job_failed(session_id, job_id, message, retryable_step)
        self.record_event(
            session_id=session_id,
            job_id=job_id,
            event_type="job_failed",
            step="failed",
            message=message,
            progress=self.session_repo.get(session_id).progress,
            payload={"retryableStep": retryable_step},
        )
        step_key = RETRYABLE_STEP_TO_STEP_KEY.get(retryable_step, "render_video")
        failed_step = self._ensure_job_step(session_id, job_id, step_key)
        self.step_service.fail_step(
            failed_step.id,
            message=message,
            retryable=True,
            retryable_step=step_key,
        )

    def mark_job_requeued_after_replan(
        self,
        session_id: str,
        failed_job_id: str,
        replacement_job_id: str,
    ):
        self.job_state_service.mark_job_requeued_after_replan(
            session_id,
            failed_job_id,
            replacement_job_id,
        )
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

    def _ensure_job_step(self, session_id: str, job_id: str, step_key: str):
        title, description, sequence = STEP_DEFINITIONS.get(
            step_key,
            ("渲染视频", "调用渲染流程，生成视频产物或失败原因。", 8),
        )
        return self.step_lifecycle.ensure_step(
            session_id=session_id,
            job_id=job_id,
            step_key=step_key,
            title=title,
            description=description,
            sequence=sequence,
        )
