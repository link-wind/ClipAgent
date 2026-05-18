import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
import backend.db.models  # noqa: F401
from backend.db.repositories import AgentJobRepository, AgentPlanRepository, AgentSessionRepository


class _FakeAssetExecutor:
    def __init__(self, clips=None, error=None):
        self.clips = clips or []
        self.error = error
        self.calls = []

    def execute(self, *, progress_service, session_id, job_id, plan):
        self.calls.append((session_id, job_id, plan.title))
        if self.error is not None:
            raise self.error
        return list(self.clips)


class _FakeRenderExecutor:
    def __init__(self, video_url="/output/final.mp4"):
        self.video_url = video_url
        self.calls = []

    def execute(self, *, progress_service, session_id, job_id, clips):
        self.calls.append((session_id, job_id, len(clips)))
        return self.video_url


class _FakeReplanService:
    def __init__(self, replacement_job_id=None):
        self.replacement_job_id = replacement_job_id
        self.calls = []

    def attempt_replan(self, *, db, progress_service, job_record, exc, retryable_step):
        self.calls.append((job_record.id, str(exc), retryable_step))
        return self.replacement_job_id


class ExecutionWorkflowServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def _create_job(self, *, status="queued"):
        with self.SessionLocal() as db:
            session = AgentSessionRepository(db).create(status="queued", current_step="任务已入队", progress=25)
            plan = AgentPlanRepository(db).create(
                session_id=session.id,
                version=1,
                title="执行链路测试",
                target_duration=8,
                style="demo",
                plan_json={
                    "title": "执行链路测试",
                    "targetDuration": 8,
                    "style": "demo",
                    "scenes": [
                        {
                            "id": 1,
                            "description": "场景",
                            "duration": 4,
                            "keywords": ["demo"],
                            "searchQuery": "demo video",
                        }
                    ],
                },
                execution_plan_json={},
                status="draft",
            )
            job = AgentJobRepository(db).create(
                session_id=session.id,
                plan_id=plan.id,
                job_type="generate_video",
                status=status,
                progress=0,
                current_step="任务已入队",
                max_attempts=3,
            )
            db.commit()
            return session.id, job.id

    def test_workflow_skips_when_job_cannot_be_claimed(self):
        from backend.app.execution.workflow_service import ExecutionWorkflowService

        _session_id, job_id = self._create_job(status="running")
        asset_executor = _FakeAssetExecutor()
        render_executor = _FakeRenderExecutor()

        ExecutionWorkflowService(
            session_factory=self.SessionLocal,
            asset_executor=asset_executor,
            render_executor=render_executor,
            replan_service=_FakeReplanService(),
        ).run_job(job_id)

        self.assertEqual(asset_executor.calls, [])
        self.assertEqual(render_executor.calls, [])

    def test_workflow_runs_search_then_render_for_claimed_job(self):
        from backend.app.execution.workflow_service import ExecutionWorkflowService

        session_id, job_id = self._create_job()
        clip = SimpleNamespace(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=4,
            caption="字幕",
            sourceDuration=8,
            trimStart=0,
            trimDuration=4,
        )
        asset_executor = _FakeAssetExecutor(clips=[clip])
        render_executor = _FakeRenderExecutor(video_url="/output/final.mp4")

        ExecutionWorkflowService(
            session_factory=self.SessionLocal,
            asset_executor=asset_executor,
            render_executor=render_executor,
            replan_service=_FakeReplanService(),
        ).run_job(job_id)

        self.assertEqual(asset_executor.calls[0][0], session_id)
        self.assertEqual(render_executor.calls, [(session_id, job_id, 1)])
        with self.SessionLocal() as db:
            job = AgentJobRepository(db).get(job_id)
            self.assertEqual(job.status, "succeeded")
            self.assertEqual(job.progress, 100)

    def test_workflow_marks_job_failed_when_search_fails(self):
        from backend.app.execution.workflow_service import ExecutionWorkflowService

        _session_id, job_id = self._create_job()
        asset_executor = _FakeAssetExecutor(error=RuntimeError("素材检索失败"))
        replan_service = _FakeReplanService(replacement_job_id=None)

        ExecutionWorkflowService(
            session_factory=self.SessionLocal,
            asset_executor=asset_executor,
            render_executor=_FakeRenderExecutor(),
            replan_service=replan_service,
        ).run_job(job_id)

        with self.SessionLocal() as db:
            job = AgentJobRepository(db).get(job_id)
            self.assertEqual(job.status, "failed")
            self.assertEqual(job.error_message, "素材检索失败")
        self.assertEqual(replan_service.calls, [(job_id, "素材检索失败", "searching")])

    def test_workflow_can_request_replan_for_search_failure(self):
        from backend.app.execution.workflow_service import ExecutionWorkflowService

        _session_id, job_id = self._create_job()
        asset_executor = _FakeAssetExecutor(error=RuntimeError("素材检索失败"))
        replan_service = _FakeReplanService(replacement_job_id="replacement-job")

        ExecutionWorkflowService(
            session_factory=self.SessionLocal,
            asset_executor=asset_executor,
            render_executor=_FakeRenderExecutor(),
            replan_service=replan_service,
        ).run_job(job_id)

        self.assertEqual(replan_service.calls, [(job_id, "素材检索失败", "searching")])
        with self.SessionLocal() as db:
            job = AgentJobRepository(db).get(job_id)
            self.assertEqual(job.status, "failed")

    def test_job_state_service_marks_job_running_and_syncs_session_fields(self):
        from backend.app.execution.job_state_service import JobStateService
        from backend.db.repositories import AgentEventRepository, AgentStepRepository

        session_id, job_id = self._create_job()

        with self.SessionLocal() as db:
            JobStateService(db).mark_job_running(session_id=session_id, job_id=job_id)
            db.commit()

        with self.SessionLocal() as db:
            job = AgentJobRepository(db).get(job_id)
            session = AgentSessionRepository(db).get(session_id)
            events = AgentEventRepository(db).list_for_job(job_id)
            steps = AgentStepRepository(db).list_for_job(job_id)

            self.assertEqual(job.status, "running")
            self.assertEqual(job.progress, 35)
            self.assertEqual(job.current_step, "正在搜索素材")
            self.assertIsNotNone(job.started_at)

            self.assertEqual(session.status, "searching")
            self.assertEqual(session.progress, 35)
            self.assertEqual(session.current_step, "正在搜索素材")
            self.assertIsNone(session.error_message)
            self.assertIsNone(session.error_retryable_step)
            self.assertEqual(events, [])
            self.assertEqual(steps, [])

    def test_event_service_records_execution_event(self):
        from backend.app.execution.event_service import ExecutionEventService
        from backend.db.repositories import AgentEventRepository

        session_id, job_id = self._create_job()

        with self.SessionLocal() as db:
            record = ExecutionEventService(db).record_event(
                session_id=session_id,
                job_id=job_id,
                event_type="job_started",
                step="searching",
                message="任务开始执行",
                progress=35,
                payload={"source": "workflow"},
            )
            record_id = record.id
            db.commit()

        with self.SessionLocal() as db:
            events = AgentEventRepository(db).list_for_job(job_id)

            self.assertEqual(len(events), 1)
            self.assertEqual(events[0].id, record_id)
            self.assertEqual(events[0].event_type, "job_started")
            self.assertEqual(events[0].step, "searching")
            self.assertEqual(events[0].message, "任务开始执行")
            self.assertEqual(events[0].progress, 35)
            self.assertEqual(events[0].payload_json, {"source": "workflow"})

    def test_artifact_service_creates_execution_artifact(self):
        from backend.app.execution.artifact_service import ExecutionArtifactService
        from backend.db.repositories import AgentArtifactRepository

        session_id, job_id = self._create_job()

        with self.SessionLocal() as db:
            record = ExecutionArtifactService(db).create_artifact(
                session_id=session_id,
                job_id=job_id,
                artifact_type="candidate_visual",
                public_url="/downloads/clip-1.mp4",
                local_path="backend/downloads/clip-1.mp4",
                scene_id="scene-1",
                source_url="https://example.com/clip-1",
                duration=4,
                metadata={"provider": "pexels"},
            )
            record_id = record.id
            db.commit()

        with self.SessionLocal() as db:
            artifacts = AgentArtifactRepository(db).list_for_job(job_id)

            self.assertEqual(len(artifacts), 1)
            self.assertEqual(artifacts[0].id, record_id)
            self.assertEqual(artifacts[0].artifact_type, "candidate_visual")
            self.assertEqual(artifacts[0].public_url, "/downloads/clip-1.mp4")
            self.assertEqual(artifacts[0].local_path, "backend/downloads/clip-1.mp4")
            self.assertEqual(artifacts[0].scene_id, "scene-1")
            self.assertEqual(artifacts[0].source_url, "https://example.com/clip-1")
            self.assertEqual(artifacts[0].duration, 4)
            self.assertEqual(artifacts[0].metadata_json, {"provider": "pexels"})

    def test_step_lifecycle_ensure_step_reuses_existing_job_step(self):
        from backend.app.execution.step_lifecycle import StepLifecycleService
        from backend.db.repositories import AgentStepRepository

        session_id, job_id = self._create_job()

        with self.SessionLocal() as db:
            service = StepLifecycleService(db)
            first = service.ensure_step(
                session_id=session_id,
                job_id=job_id,
                step_key="search_assets",
                title="搜索素材",
                description="根据最终方案搜索候选素材并记录搜索结果。",
                sequence=6,
            )
            second = service.ensure_step(
                session_id=session_id,
                job_id=job_id,
                step_key="search_assets",
                title="搜索素材",
                description="根据最终方案搜索候选素材并记录搜索结果。",
                sequence=6,
            )
            steps = AgentStepRepository(db).list_for_job(job_id)

            self.assertEqual(first.id, second.id)
            self.assertEqual(len(steps), 1)
            self.assertEqual(steps[0].step_key, "search_assets")
            self.assertEqual(steps[0].status, "running")


if __name__ == "__main__":
    unittest.main()
