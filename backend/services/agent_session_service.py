import re
from typing import Optional

from backend.db.repositories import (
    AgentMessageRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.models.agent import AgentSession, EditPlan, PlanScene
from backend.services.agent_read_service import AgentReadService
from backend.services.grounding_service import grounding_service
from backend.services.planner_orchestrator import PlannerOrchestrator
from backend.services.planner_projection import execution_plan_to_edit_plan


PLAN_READY_MESSAGE = "我已经生成剪辑方案，你可以继续修改或确认开始。"
GROUNDING_READY_MESSAGE = "我已经整理出候选产品画面，请先确认后再生成剪辑方案。"


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
                    message_record = message_repo.create(session_id=session_id, role="user", content=prompt)
                    planner_orchestrator = PlannerOrchestrator()
                    plan_record = planner_orchestrator.persist_initial_plan(
                        db=db,
                        session_record=session_record,
                        message_record=message_record,
                    )
                    session_record.grounding_status = None
                    session_record.grounding_summary_json = {}
                    session_record.selected_candidate_ids_json = []
                    session_repo.set_current_plan(session_id, plan_record.id)
                    plan = execution_plan_to_edit_plan(plan_record.execution_plan_json)
                    self._apply_plan_to_session(session_record, plan)
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
                if self._should_start_grounding(session_record, latest_plan):
                    grounding_summary = grounding_service.build_grounding_summary(
                        content,
                        existing=session_record.grounding_summary_json,
                    )
                    self._apply_grounding_to_session(session_record, grounding_summary)
                    session_repo.update_grounding_state(
                        session_id,
                        grounding_status=grounding_summary.status,
                        grounding_summary_json=grounding_summary.model_dump(mode="json"),
                        selected_candidate_ids_json=[],
                    )
                    self._append_grounding_ready_message(message_repo, session_id)
                    db.commit()
                    return self.read_service.read_session(session_id)

                should_create_plan = (
                    latest_plan is None
                    or session_record.status == "plan_ready"
                    or (
                        session_record.status == "failed"
                        and session_record.error_retryable_step == "planning"
                    )
                )
                if should_create_plan:
                    plan = self._build_next_plan(latest_plan, content)
                    self._apply_plan_to_session(session_record, plan)
                    next_version = 1 if latest_plan is None else latest_plan.version + 1
                    plan_repo.create(
                        session_id=session_id,
                        version=next_version,
                        title=plan.title,
                        target_duration=int(plan.targetDuration),
                        style=plan.style,
                        plan_json=plan.model_dump(mode="json"),
                        execution_plan_json=plan.model_dump(mode="json"),
                    )
                    self._append_plan_ready_message(message_repo, session_id)

                db.commit()
            except Exception:
                db.rollback()
                raise

        return self.read_service.read_session(session_id)

    def confirm_grounding_candidates(self, session_id: str, candidate_ids: list[str]) -> AgentSession:
        if not candidate_ids:
            raise ValueError("Candidate ids are required")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            plan_repo = AgentPlanRepository(db)

            try:
                session_record = session_repo.get(session_id)
                if session_record is None:
                    raise KeyError(session_id)
                if not self._can_confirm_grounding(session_record):
                    raise RuntimeError("Session is not awaiting confirmation of grounding candidates")

                grounding_summary = session_record.grounding_summary_json or {}
                available_candidates = grounding_summary.get("candidates", []) or []
                candidate_lookup = {candidate.get("id"): candidate for candidate in available_candidates}
                missing_candidate_ids = [candidate_id for candidate_id in candidate_ids if candidate_id not in candidate_lookup]
                if missing_candidate_ids:
                    raise ValueError("Unknown grounding candidate id")

                latest_plan = plan_repo.get_latest_for_session(session_id)
                if latest_plan is None:
                    messages = message_repo.list_for_session(session_id)
                    latest_user_message = next(
                        (message for message in reversed(messages) if message.role == "user"),
                        None,
                    )
                    if latest_user_message is None:
                        grounded_plan = self._build_grounded_plan_from_candidates(
                            prompt=session_record.title or "",
                            grounding_summary=grounding_summary,
                            candidate_ids=candidate_ids,
                        )
                        self._apply_plan_to_session(session_record, grounded_plan)
                        next_plan = plan_repo.create(
                            session_id=session_id,
                            version=1,
                            title=grounded_plan.title,
                            target_duration=int(grounded_plan.targetDuration),
                            style=grounded_plan.style,
                            plan_json=grounded_plan.model_dump(mode="json"),
                            execution_plan_json=grounded_plan.model_dump(mode="json"),
                        )
                    else:
                        planner_orchestrator = PlannerOrchestrator()
                        initial_plan = planner_orchestrator.persist_initial_plan(
                            db=db,
                            session_record=session_record,
                            message_record=latest_user_message,
                        )
                        session_repo.set_current_plan(session_id, initial_plan.id)
                        next_plan = planner_orchestrator.persist_grounding_replan(
                            db=db,
                            session_record=session_record,
                            candidate_ids=candidate_ids,
                        )
                        grounded_plan = execution_plan_to_edit_plan(next_plan.execution_plan_json)
                        self._apply_plan_to_session(session_record, grounded_plan)
                        session_repo.set_current_plan(session_id, next_plan.id)
                else:
                    planner_orchestrator = PlannerOrchestrator()
                    next_plan = planner_orchestrator.persist_grounding_replan(
                        db=db,
                        session_record=session_record,
                        candidate_ids=candidate_ids,
                    )
                    grounded_plan = execution_plan_to_edit_plan(next_plan.execution_plan_json)
                    self._apply_plan_to_session(session_record, grounded_plan)
                    session_repo.set_current_plan(session_id, next_plan.id)

                session_repo.update_grounding_state(
                    session_id,
                    grounding_status="confirmed",
                    grounding_summary_json={
                        **grounding_summary,
                        "status": "confirmed",
                        "selectedCandidateIds": candidate_ids,
                    },
                    selected_candidate_ids_json=candidate_ids,
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

    def _append_grounding_ready_message(self, message_repo: AgentMessageRepository, session_id: str) -> None:
        # 追加候选确认提示消息
        message_repo.create(
            session_id=session_id,
            role="assistant",
            content=GROUNDING_READY_MESSAGE,
        )

    def _is_editable(self, session_record) -> bool:
        # 仅允许空闲、方案可编辑或规划失败重试
        if session_record.status in {"idle", "plan_ready"}:
            return True
        return (
            session_record.status == "failed"
            and session_record.error_retryable_step == "planning"
        )

    def _build_next_plan(self, latest_plan, content: str) -> EditPlan:
        if latest_plan is None:
            return self._fallback_plan(content)

        current_plan = self._load_edit_plan(latest_plan)
        updated_plan = self._apply_scene_keyword_updates(current_plan, content)
        if updated_plan is not None:
            return updated_plan

        return current_plan.model_copy(deep=True)

    def _load_edit_plan(self, plan_record) -> EditPlan:
        execution_plan_json = getattr(plan_record, "execution_plan_json", None) or {}
        if execution_plan_json.get("scenes"):
            return EditPlan.model_validate(execution_plan_json)
        return EditPlan.model_validate(plan_record.plan_json)

    def _apply_scene_keyword_updates(self, plan: EditPlan, content: str) -> EditPlan | None:
        updates = self._extract_scene_keyword_updates(content)
        if not updates:
            return None

        updated_scenes: list[PlanScene] = []
        changed = False
        for scene in plan.scenes:
            keywords = updates.get(scene.id)
            if not keywords:
                updated_scenes.append(scene.model_copy(deep=True))
                continue

            changed = True
            updated_scenes.append(
                scene.model_copy(
                    update={
                        "keywords": keywords,
                        "searchQuery": " ".join(keywords),
                    }
                )
            )

        if not changed:
            return None

        return plan.model_copy(update={"scenes": updated_scenes})

    def _extract_scene_keyword_updates(self, content: str) -> dict[int, list[str]]:
        updates: dict[int, list[str]] = {}
        pattern = re.compile(r"场景\s*(\d+)\s*[:：]\s*([^；;\n]+)")
        for raw_scene_id, raw_keywords in pattern.findall(content):
            scene_id = int(raw_scene_id)
            keywords = self._split_keywords(raw_keywords)
            if keywords:
                updates[scene_id] = keywords
        return updates

    def _split_keywords(self, raw_keywords: str) -> list[str]:
        parts = re.split(r"[\s,，、/|]+", raw_keywords.strip())
        return [part.strip() for part in parts if part.strip()]

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

    def _apply_grounding_to_session(self, session_record, grounding_summary) -> None:
        session_record.status = "plan_ready"
        session_record.current_step = "等待确认候选产品画面"
        session_record.progress = 20
        session_record.title = grounding_summary.productName or "智能剪辑短片"
        session_record.grounding_status = grounding_summary.status
        session_record.grounding_summary_json = grounding_summary.model_dump(mode="json")
        session_record.selected_candidate_ids_json = []

    def _build_grounded_plan_from_candidates(self, prompt: str, grounding_summary, candidate_ids: list[str]) -> EditPlan:
        selected_candidates = []
        candidate_lookup = {candidate["id"]: candidate for candidate in grounding_summary.get("candidates", []) or []}
        for candidate_id in candidate_ids:
            candidate = candidate_lookup[candidate_id]
            selected_candidates.append(candidate)

        title = grounding_summary.get("productName") or self._infer_plan_title_from_prompt(prompt)
        if not title and selected_candidates:
            title = selected_candidates[0].get("productName") or selected_candidates[0].get("title") or "智能剪辑短片"

        feature_hints = grounding_summary.get("featureHints", []) or []
        audience = grounding_summary.get("audience", "") or ""
        style_hint = grounding_summary.get("styleHint", "") or "快节奏社媒短片"
        selected_titles = [candidate.get("title", "") for candidate in selected_candidates if candidate.get("title")]

        scenes = [
            PlanScene(
                id=1,
                description="确认品牌与画面方向",
                keywords=selected_titles[:3] or feature_hints[:3] or [title],
                duration=6,
                searchQuery=" ".join((selected_titles[:3] or feature_hints[:3] or [title])) if (selected_titles or feature_hints or title) else "",
            ),
            PlanScene(
                id=2,
                description="展示重点候选素材",
                keywords=feature_hints[:3] or selected_titles[:3] or [audience or title],
                duration=8,
                searchQuery=" ".join(feature_hints[:3] or selected_titles[:3] or [audience or title]),
            ),
            PlanScene(
                id=3,
                description="补充真实使用语境",
                keywords=[audience] if audience else (selected_titles[:2] or [title]),
                duration=10,
                searchQuery=" ".join(([audience] if audience else (selected_titles[:2] or [title]))),
            ),
            PlanScene(
                id=4,
                description="收束到行动号召",
                keywords=[style_hint] if style_hint else [title],
                duration=6,
                searchQuery=style_hint or title,
            ),
        ]

        return EditPlan(
            title=title or "智能剪辑短片",
            targetDuration=30,
            style=style_hint or "快节奏社媒短片",
            scenes=scenes,
        )

    def _infer_plan_title_from_prompt(self, prompt: str) -> str:
        match = re.search(r"给\s*([^\s，。,；;]+)", prompt or "")
        return match.group(1).strip() if match else ""

    @staticmethod
    def _requires_grounding_confirmation(session_record) -> bool:
        grounding_summary = getattr(session_record, "grounding_summary_json", None) or {}
        grounding_status = getattr(session_record, "grounding_status", None)
        selected_candidate_ids = getattr(session_record, "selected_candidate_ids_json", None) or []
        if selected_candidate_ids or grounding_status == "confirmed":
            return False
        if grounding_status == "needs_confirmation":
            return True
        return any(
            grounding_summary.get(key)
            for key in (
                "productName",
                "audience",
                "styleHint",
                "featureHints",
                "searchQueries",
                "candidates",
            )
        )

    def _should_start_grounding(self, session_record, latest_plan) -> bool:
        if latest_plan is None and getattr(session_record, "grounding_status", None) != "confirmed":
            return True
        return self._requires_grounding_confirmation(session_record)

    @staticmethod
    def _can_confirm_grounding(session_record) -> bool:
        if getattr(session_record, "status", None) not in {"idle", "plan_ready"}:
            return False
        if getattr(session_record, "grounding_status", None) != "needs_confirmation":
            return False
        return bool((getattr(session_record, "grounding_summary_json", None) or {}).get("candidates"))
