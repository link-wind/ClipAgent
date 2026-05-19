import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.repositories import (
    AgentJobRepository,
    AgentObservationRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.app.execution.execution_service import AgentExecutionService
from backend.app.agent.session_service import AgentSessionService
from backend.tasks.agent_tasks import run_agent_job


class AgentPlannerPhase4Tests(unittest.TestCase):
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

    def test_execution_feedback_replan_creates_plan_vnext_and_replacement_job(self):
        session_service = AgentSessionService(session_factory=self.session_factory)
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )

        session = session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        confirmed = execution_service.confirm_session(session.id)
        job_id = confirmed.activeJobId

        async def failing_search_runner(_session_id, _scenes):
            raise RuntimeError("素材检索失败")

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            plan_repo = AgentPlanRepository(db)
            observation_repo = AgentObservationRepository(db)
            session_repo = AgentSessionRepository(db)

            jobs = job_repo.list_recent(limit=10)
            plans = plan_repo.list_for_session(session.id)
            observations = observation_repo.list_for_session(session.id)
            session_record = session_repo.get(session.id)

            self.assertEqual(plans[-1].trigger_type, "execution_feedback")
            self.assertEqual(plans[-1].parent_plan_id, plans[-2].id)
            self.assertEqual(observations[-1].observation_type, "execution_feedback")
            self.assertEqual(jobs[0].status, "queued")
            self.assertEqual(jobs[0].plan_id, plans[-1].id)
            self.assertEqual(session_record.current_plan_id, plans[-1].id)

    def test_execution_feedback_replan_persists_platform_blocked_query_rewrite(self):
        session_service = AgentSessionService(session_factory=self.session_factory)
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )

        session = session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        confirmed = execution_service.confirm_session(session.id)
        job_id = confirmed.activeJobId

        class FakeSceneSearchFailure(RuntimeError):
            def __init__(self, message: str, failed_scene_ids: list[int]):
                super().__init__(message)
                self.failed_scene_ids = failed_scene_ids

        async def failing_search_runner(_session_id, _scenes):
            raise FakeSceneSearchFailure(
                "YouTube 当前要求 PO Token，公开视频下载被平台策略限制。",
                [1],
            )

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            plans = AgentPlanRepository(db).list_for_session(session.id)

        self.assertEqual(
            plans[-1].execution_plan_json["scenes"][0]["searchQuery"],
            "software dashboard laptop",
        )
        self.assertEqual(
            plans[-1].plan_json["replanHistory"][-1]["failureCategory"],
            "platform_blocked",
        )
        self.assertEqual(
            plans[-1].plan_json["replanHistory"][-1]["rewriteStrategy"],
            "stock_footage_fallback",
        )
