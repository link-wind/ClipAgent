from typing import Optional

from backend.db.repositories import (
    AgentMessageRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.models.agent import AgentSession, EditPlan, PlanScene
from backend.services.agent_read_service import AgentReadService


PLAN_READY_MESSAGE = "我已经生成剪辑方案，你可以继续修改或确认开始。"


class AgentSessionService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.read_service = AgentReadService(session_factory=session_factory)

    def create_session(self, prompt: Optional[str] = None) -> AgentSession:
        # 创建会话，必要时落首条消息和计划
        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            plan_repo = AgentPlanRepository(db)

            try:
                session_record = session_repo.create(status="idle", current_step="", progress=0)
                session_id = session_record.id

                if prompt and prompt.strip():
                    message_repo.create(session_id=session_id, role="user", content=prompt)
                    plan = self._fallback_plan(prompt)
                    self._apply_plan_to_session(session_record, plan)
                    plan_repo.create(
                        session_id=session_id,
                        version=1,
                        title=plan.title,
                        target_duration=int(plan.targetDuration),
                        style=plan.style,
                        plan_json=plan.model_dump(mode="json"),
                    )
                    self._append_plan_ready_message(message_repo, session_id)

                db.commit()
            except Exception:
                db.rollback()
                raise

        return self.read_service.read_session(session_id)

    def get_session(self, session_id: str) -> AgentSession:
        # 读取会话
        return self.read_service.read_session(session_id)

    def add_user_message(self, session_id: str, content: str) -> AgentSession:
        # 追加用户消息，并在需要时补计划
        if not content.strip():
            raise ValueError("Message content is required")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            plan_repo = AgentPlanRepository(db)

            try:
                session_record = session_repo.get(session_id)
                if session_record is None:
                    raise KeyError(session_id)
                if not self._is_editable(session_record):
                    raise RuntimeError(f"Session is not editable while {session_record.status}")

                message_repo.create(session_id=session_id, role="user", content=content)
                latest_plan = plan_repo.get_latest_for_session(session_id)
                should_create_plan = latest_plan is None or session_record.status == "plan_ready"
                if should_create_plan:
                    plan = self._fallback_plan(
                        content,
                        title=latest_plan.title if latest_plan else "智能剪辑短片",
                    )
                    self._apply_plan_to_session(session_record, plan)
                    next_version = 1 if latest_plan is None else latest_plan.version + 1
                    plan_repo.create(
                        session_id=session_id,
                        version=next_version,
                        title=plan.title,
                        target_duration=int(plan.targetDuration),
                        style=plan.style,
                        plan_json=plan.model_dump(mode="json"),
                    )
                    self._append_plan_ready_message(message_repo, session_id)

                db.commit()
            except Exception:
                db.rollback()
                raise

        return self.read_service.read_session(session_id)

    def _apply_plan_to_session(self, session_record, plan: EditPlan) -> None:
        # 更新会话聚合字段
        session_record.status = "plan_ready"
        session_record.current_step = "剪辑方案已生成"
        session_record.progress = 20
        session_record.title = plan.title

    def _append_plan_ready_message(self, message_repo: AgentMessageRepository, session_id: str) -> None:
        # 追加方案提示消息
        message_repo.create(
            session_id=session_id,
            role="assistant",
            content=PLAN_READY_MESSAGE,
        )

    def _is_editable(self, session_record) -> bool:
        # 仅允许空闲、方案可编辑或规划失败重试
        if session_record.status in {"idle", "plan_ready"}:
            return True
        return (
            session_record.status == "failed"
            and session_record.error_retryable_step == "planning"
        )

    def _fallback_plan(self, prompt: str, title: str = "智能剪辑短片") -> EditPlan:
        # 生成最小兜底方案
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
