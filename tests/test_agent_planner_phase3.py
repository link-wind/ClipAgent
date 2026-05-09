import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.repositories import (
    AgentObservationRepository,
    AgentPlanRepository,
    AgentSessionRepository,
)
from backend.services.agent_session_service import AgentSessionService


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
        service = AgentSessionService(session_factory=self.session_factory)

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
