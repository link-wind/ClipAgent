import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.db.repositories import AgentObservationRepository, AgentPlanRepository
from backend.services.agent_session_service import AgentSessionService


class AgentPlannerPhase2Tests(unittest.TestCase):
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

    def test_confirm_grounding_persists_observation_and_plan_v2(self):
        service = AgentSessionService(session_factory=self.session_factory)
        session = service.create_session()
        awaiting = service.add_user_message(session.id, "给 Notion AI 做一个 30 秒产品亮点视频")
        selected_ids = [candidate.id for candidate in awaiting.grounding.candidates[:2]]

        with self.session_factory() as db:
            initial_plan = AgentPlanRepository(db).get_latest_for_session(session.id)

        self.assertIsNone(initial_plan)

        grounded = service.confirm_grounding_candidates(session.id, selected_ids)

        self.assertEqual(grounded.grounding.status, "confirmed")
        self.assertEqual(grounded.grounding.selectedCandidateIds, selected_ids)

        with self.session_factory() as db:
            latest = AgentPlanRepository(db).get_latest_for_session(session.id)
            observations = AgentObservationRepository(db).list_for_session(session.id)
            version_one = next((plan for plan in AgentPlanRepository(db).list_for_session(session.id) if plan.version == 1), None)

            self.assertEqual(latest.version, 2)
            self.assertEqual(latest.trigger_type, "grounding_confirmation")
            self.assertIsNotNone(version_one)
            self.assertEqual(latest.parent_plan_id, version_one.id)
            self.assertEqual(observations[-1].observation_type, "grounding_confirmation")
