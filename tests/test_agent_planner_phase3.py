import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.repositories import (
    AgentObservationRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.app.agent.session_service import AgentSessionService


class AgentPlannerPhase3Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_post_plan_user_revision_persists_observation_and_plan_vnext(self):
        from backend.app.planning.runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        initial_agent, initial_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        class _FakeRevisionRuntime:
            def build_plan_from_brief(self, _brief):
                return initial_agent, initial_execution

            def replan_after_user_revision(self, current_agent, current_execution, revision_feedback):
                updated_keywords = revision_feedback.sceneKeywordUpdates[1]
                next_agent = current_agent.model_copy(
                    update={
                        "summary": "更偏商务演示与销售沟通的版本",
                        "understanding": current_agent.understanding.model_copy(
                            update={
                                "audience": "销售团队",
                                "styleHint": "商务演示风格",
                            },
                            deep=True,
                        ),
                        "scenes": [
                            current_agent.scenes[0].model_copy(
                                update={
                                    "description": "城市与车流开场，建立商务节奏",
                                    "keywords": updated_keywords,
                                },
                                deep=True,
                            ),
                            *[scene.model_copy(deep=True) for scene in current_agent.scenes[1:]],
                        ],
                        "replanHistory": [
                            *current_agent.replanHistory,
                            {
                                "triggerType": "user_revision",
                                "summary": "已根据最新修改意见完成计划重写",
                                "message": revision_feedback.message.strip(),
                                "runtime": "langchain",
                            },
                        ],
                    },
                    deep=True,
                )
                next_execution = current_execution.model_copy(
                    update={
                        "style": "商务演示风格",
                        "scenes": [
                            current_execution.scenes[0].model_copy(
                                update={
                                    "description": "城市与车流开场，建立商务节奏",
                                    "keywords": updated_keywords,
                                    "searchQuery": "城市 车流 黄昏",
                                },
                                deep=True,
                            ),
                            *[scene.model_copy(deep=True) for scene in current_execution.scenes[1:]],
                        ],
                    },
                    deep=True,
                )
                return next_agent, next_execution, "已根据最新修改意见完成计划重写"

        service = AgentSessionService(session_factory=self.session_factory)

        with patch(
            "backend.app.planning.graph.get_planner_runtime",
            return_value=_FakeRevisionRuntime(),
        ):
            session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
            updated = service.add_user_message(
                session.id,
                "整体再商务一点，目标受众改成销售团队，场景1：城市 车流 黄昏",
            )

        self.assertEqual(updated.status.value, "plan_ready")
        self.assertIsNotNone(updated.plan)

        with self.session_factory() as db:
            plan_repo = AgentPlanRepository(db)
            observation_repo = AgentObservationRepository(db)
            session_repo = AgentSessionRepository(db)

            plans = plan_repo.list_for_session(session.id)
            latest = plans[-1]
            previous = plans[-2]
            observations = observation_repo.list_for_session(session.id)
            session_record = session_repo.get(session.id)

            self.assertEqual(len(plans), 2)
            self.assertEqual(previous.version, 1)
            self.assertEqual(latest.version, 2)
            self.assertEqual(latest.parent_plan_id, previous.id)
            self.assertEqual(latest.trigger_type, "user_revision")
            self.assertEqual(observations[-1].observation_type, "user_revision")
            self.assertEqual(session_record.current_plan_id, latest.id)
            self.assertEqual(session_record.planner_trace_json["revisionRuntime"], "langchain")
            self.assertFalse(session_record.planner_trace_json["fallbackUsed"])
            self.assertEqual(latest.execution_plan_json["style"], "商务演示风格")
            self.assertEqual(latest.execution_plan_json["scenes"][0]["searchQuery"], "城市 车流 黄昏")

    def test_post_plan_user_revision_clears_stale_fallback_reason_after_success(self):
        from backend.app.planning.runtime_deterministic import DeterministicPlannerRuntime

        runtime = DeterministicPlannerRuntime()
        initial_agent, initial_execution = runtime.build_plan_from_brief(
            "给 Notion AI 做一个 30 秒产品亮点视频"
        )

        class _FakeRevisionRuntime:
            def build_plan_from_brief(self, _brief):
                return initial_agent, initial_execution

            def replan_after_user_revision(self, current_agent, current_execution, revision_feedback):
                updated_keywords = revision_feedback.sceneKeywordUpdates[1]
                next_agent = current_agent.model_copy(
                    update={
                        "replanHistory": [
                            *current_agent.replanHistory,
                            {
                                "triggerType": "user_revision",
                                "summary": "已根据最新修改意见完成计划重写",
                                "message": revision_feedback.message.strip(),
                                "runtime": "langchain",
                            },
                        ],
                    },
                    deep=True,
                )
                next_execution = current_execution.model_copy(
                    update={
                        "style": "商务演示风格",
                        "scenes": [
                            current_execution.scenes[0].model_copy(
                                update={
                                    "keywords": updated_keywords,
                                    "searchQuery": "城市 车流 黄昏",
                                },
                                deep=True,
                            ),
                            *[scene.model_copy(deep=True) for scene in current_execution.scenes[1:]],
                        ],
                    },
                    deep=True,
                )
                return next_agent, next_execution, "已根据最新修改意见完成计划重写"

        service = AgentSessionService(session_factory=self.session_factory)

        with patch(
            "backend.app.planning.graph.get_planner_runtime",
            return_value=_FakeRevisionRuntime(),
        ):
            session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
            with self.session_factory() as db:
                session_record = AgentSessionRepository(db).get(session.id)
                session_record.planner_trace_json = {
                    "lastPlanningState": "replanning_complete",
                    "triggerType": "user_revision",
                    "revisionRuntime": "deterministic_fallback",
                    "fallbackUsed": True,
                    "fallbackReason": "stale fallback reason",
                }
                db.commit()

            service.add_user_message(
                session.id,
                "整体再商务一点，目标受众改成销售团队，场景1：城市 车流 黄昏",
            )

        with self.session_factory() as db:
            session_record = AgentSessionRepository(db).get(session.id)

            self.assertEqual(session_record.planner_trace_json["revisionRuntime"], "langchain")
            self.assertFalse(session_record.planner_trace_json["fallbackUsed"])
            self.assertNotIn("fallbackReason", session_record.planner_trace_json)
