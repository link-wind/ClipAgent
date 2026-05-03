import uuid
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Literal, Optional

from backend.models.agent import AgentError, AgentMessage, AgentSession, AgentStatus, ClipInfo, EditPlan, PlanScene


SearchRunner = Callable[[str, List[PlanScene]], Awaitable[List[ClipInfo]]]
RenderRunner = Callable[[str, List[ClipInfo], str], Awaitable[str]]


class AgentService:
    def __init__(self):
        self.sessions: Dict[str, AgentSession] = {}

    def sync_session(self, session: AgentSession) -> AgentSession:
        # 同步数据库会话到兼容缓存
        self.sessions[session.id] = session
        return session

    def create_session(self, prompt: Optional[str] = None) -> AgentSession:
        session = AgentSession(id=str(uuid.uuid4()))
        self.sessions[session.id] = session
        if prompt and prompt.strip():
            session.messages.append(self._message("user", prompt))
            self._set_plan(session, self._fallback_plan(prompt))
        return session

    def get_session(self, session_id: str) -> AgentSession:
        return self.sessions[session_id]

    def add_user_message(self, session_id: str, content: str) -> AgentSession:
        if not content.strip():
            raise ValueError("Message content is required")

        session = self.sessions[session_id]
        if not self._is_editable(session):
            raise RuntimeError(f"Session is not editable while {session.status.value}")

        session.messages.append(self._message("user", content))
        if self._is_planning_retry(session):
            title = session.plan.title if session.plan is not None else "智能剪辑短片"
            self._set_plan(session, self._fallback_plan(content, title=title))
        elif session.plan is None:
            self._set_plan(session, self._fallback_plan(content))
        elif session.status == AgentStatus.PLAN_READY:
            self._set_plan(session, self._fallback_plan(content, title=session.plan.title))
        return session

    def confirm_session(self, session_id: str) -> AgentSession:
        session = self.sessions[session_id]
        if session.status not in (AgentStatus.IDLE, AgentStatus.PLAN_READY):
            raise RuntimeError(f"Session cannot be confirmed while {session.status.value}")

        if session.plan is None:
            session.status = AgentStatus.FAILED
            session.progress = 0
            session.currentStep = "没有可执行的剪辑方案"
            session.error = AgentError(message="没有可执行的剪辑方案", retryableStep="planning")
            return session

        session.status = AgentStatus.SEARCHING
        session.progress = 30
        session.currentStep = "正在搜索素材"
        session.error = None
        return session

    async def run_confirmed_session(
        self,
        session_id: str,
        search_runner: Optional[SearchRunner] = None,
        render_runner: Optional[RenderRunner] = None,
    ) -> AgentSession:
        session = self.sessions[session_id]
        if session.plan is None:
            session.status = AgentStatus.FAILED
            session.progress = 0
            session.currentStep = "没有可执行的剪辑方案"
            session.error = AgentError(message="没有可执行的剪辑方案", retryableStep="planning")
            return session

        if search_runner is None:
            from backend.services.search_service import search_and_download_agent_clips

            search_runner = search_and_download_agent_clips
        if render_runner is None:
            from backend.services.render_service import render_video

            render_runner = render_video

        try:
            session.status = AgentStatus.SEARCHING
            session.progress = 35
            session.currentStep = "正在搜索素材"
            session.clips = []
            session.videoUrl = None
            session.error = None

            clips = await search_runner(session.id, session.plan.scenes)
            if not clips:
                raise RuntimeError("没有下载到可用素材")

            session.status = AgentStatus.DOWNLOADING
            session.progress = 60
            session.currentStep = "素材已下载，准备渲染"
            session.clips = clips

            session.status = AgentStatus.RENDERING
            session.progress = 80
            session.currentStep = "正在合成视频"
            session.videoUrl = await render_runner(session.id, clips, f"{session.id}.mp4")

            session.status = AgentStatus.DONE
            session.progress = 100
            session.currentStep = "完成"
            session.messages.append(self._message("assistant", "视频已经生成，可以预览或下载。"))
        except Exception as exc:
            session.status = AgentStatus.FAILED
            session.error = AgentError(message=str(exc), retryableStep=self._retryable_step_for_failure(session))
            session.currentStep = f"处理失败：{exc}"

        return session

    def _is_editable(self, session: AgentSession) -> bool:
        if session.status in (AgentStatus.IDLE, AgentStatus.PLAN_READY):
            return True
        return self._is_planning_retry(session)

    def _is_planning_retry(self, session: AgentSession) -> bool:
        return (
            session.status == AgentStatus.FAILED
            and session.error is not None
            and session.error.retryableStep == "planning"
        )

    def _retryable_step_for_failure(self, session: AgentSession) -> str:
        if session.status in (AgentStatus.RENDERING, AgentStatus.DONE):
            return "rendering"
        if session.clips:
            return "rendering"
        return "searching"

    def _set_plan(self, session: AgentSession, plan: EditPlan) -> None:
        session.status = AgentStatus.PLAN_READY
        session.plan = plan
        session.error = None
        session.progress = 20
        session.currentStep = "剪辑方案已生成"
        session.messages.append(self._message("assistant", "我已经生成剪辑方案，你可以继续修改或确认开始。"))

    def _message(self, role: Literal["user", "assistant", "system"], content: str) -> AgentMessage:
        return AgentMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            createdAt=datetime.now(timezone.utc).isoformat(),
        )

    def _fallback_plan(self, prompt: str, title: str = "智能剪辑短片") -> EditPlan:
        return EditPlan(
            title=title,
            targetDuration=30,
            style="快节奏社媒短片",
            scenes=[
                PlanScene(
                    id=1,
                    description="开场建立氛围",
                    keywords=["technology", "city", "motion"],
                    duration=6,
                    searchQuery="technology city motion",
                ),
                PlanScene(
                    id=2,
                    description="展示核心功能或主题",
                    keywords=["product", "interface", "detail"],
                    duration=8,
                    searchQuery="product interface detail",
                ),
                PlanScene(
                    id=3,
                    description="呈现真实使用场景",
                    keywords=["people", "work", "collaboration"],
                    duration=10,
                    searchQuery="people work collaboration",
                ),
                PlanScene(
                    id=4,
                    description="收束到品牌和行动号召",
                    keywords=["brand", "clean", "ending"],
                    duration=6,
                    searchQuery="clean brand ending",
                ),
            ],
        )


agent_service = AgentService()
