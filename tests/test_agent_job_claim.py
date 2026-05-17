import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


class AgentJobClaimTests(unittest.TestCase):
    def setUp(self):
        from backend.db.base import Base
        import backend.db.models  # noqa: F401

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def _create_job(self, status: str):
        from backend.db.repositories import AgentJobRepository

        return AgentJobRepository(self.db).create(
            job_type="render",
            status=status,
            progress=0,
            current_step="等待执行",
        )

    def test_try_claim_queued_job_marks_running(self):
        from backend.db.repositories import AgentJobRepository

        job = self._create_job("queued")
        claimed = AgentJobRepository(self.db).try_claim_job(job.id)

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.id, job.id)
        self.assertEqual(claimed.status, "running")
        self.assertEqual(claimed.progress, 35)
        self.assertEqual(claimed.current_step, "正在搜索素材")
        self.assertIsNotNone(claimed.started_at)

    def test_try_claim_running_job_returns_none(self):
        from backend.db.repositories import AgentJobRepository

        job = self._create_job("running")
        claimed = AgentJobRepository(self.db).try_claim_job(job.id)

        self.assertIsNone(claimed)
        self.assertEqual(AgentJobRepository(self.db).get(job.id).status, "running")

    def test_try_claim_succeeded_job_returns_none(self):
        from backend.db.repositories import AgentJobRepository

        job = self._create_job("succeeded")
        claimed = AgentJobRepository(self.db).try_claim_job(job.id)

        self.assertIsNone(claimed)
        self.assertEqual(AgentJobRepository(self.db).get(job.id).status, "succeeded")

    def test_try_claim_missing_job_returns_none(self):
        from backend.db.repositories import AgentJobRepository

        claimed = AgentJobRepository(self.db).try_claim_job("missing-job-id")

        self.assertIsNone(claimed)


if __name__ == "__main__":
    unittest.main()
