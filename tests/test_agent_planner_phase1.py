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
from backend.app.agent.session_service import AgentSessionService


class AgentPlannerPhase1Tests(unittest.TestCase):
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

    def test_create_session_persists_initial_plan_and_observation(self):
        service = AgentSessionService(session_factory=self.session_factory)

        session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")

        self.assertEqual(session.status.value, "plan_ready")
        self.assertIsNotNone(session.plan)

        with self.session_factory() as db:
            session_record = AgentSessionRepository(db).get(session.id)
            plan_record = AgentPlanRepository(db).get_latest_for_session(session.id)
            observations = AgentObservationRepository(db).list_for_session(session.id)

            self.assertIsNotNone(session_record.current_plan_id)
            self.assertEqual(session_record.current_plan_id, plan_record.id)
            self.assertEqual(plan_record.version, 1)
            self.assertEqual(plan_record.trigger_type, "initial_brief")
            self.assertEqual(len(observations), 1)
            self.assertEqual(observations[0].observation_type, "user_message")
