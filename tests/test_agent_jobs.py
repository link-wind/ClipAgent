import asyncio
import importlib
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.api.agent as agent_api_module
from backend.db.base import Base
from backend.main import app
from backend.services.agent_session_service import AgentSessionService


class CeleryContractTests(unittest.TestCase):
    def test_agent_task_entrypoint_exists(self):
        from backend.tasks.agent_tasks import run_agent_job

        self.assertTrue(callable(run_agent_job))

    def test_celery_app_subprocess_registers_agent_job_task(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from backend.tasks.celery_app import celery_app; "
                    "print('backend.tasks.agent_tasks.run_agent_job' in celery_app.tasks)"
                ),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertEqual(result.stdout.strip(), "True")

    def test_celery_app_registers_agent_job_task(self):
        from backend.tasks.celery_app import celery_app

        self.assertIn("backend.tasks.agent_tasks.run_agent_job", celery_app.tasks)


class ClipInfoContractTests(unittest.TestCase):
    def test_clip_info_supports_trim_metadata(self):
        from backend.models.agent import ClipInfo

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/video",
            localPath="backend/downloads/demo.mp4",
            publicUrl="/downloads/demo.mp4",
            duration=6.0,
            sourceDuration=18.0,
            trimStart=4.2,
            trimDuration=6.0,
        )

        self.assertEqual(clip.sourceDuration, 18.0)
        self.assertEqual(clip.trimStart, 4.2)
        self.assertEqual(clip.trimDuration, 6.0)


class ClipTrimCalculationTests(unittest.TestCase):
    def test_calculate_trim_window_prefers_middle_front_for_long_source(self):
        from backend.services.search_service import calculate_trim_window

        trim_start, trim_duration = calculate_trim_window(
            source_duration=20.0,
            target_duration=6.0,
        )

        self.assertAlmostEqual(trim_start, 4.9)
        self.assertEqual(trim_duration, 6.0)

    def test_calculate_trim_window_uses_full_source_when_shorter_than_target(self):
        from backend.services.search_service import calculate_trim_window

        trim_start, trim_duration = calculate_trim_window(
            source_duration=4.5,
            target_duration=6.0,
        )

        self.assertEqual(trim_start, 0.0)
        self.assertEqual(trim_duration, 4.5)


class SearchClipAssemblyTests(unittest.TestCase):
    def test_search_and_download_agent_clips_populates_trim_metadata(self):
        from backend.models.agent import PlanScene
        from backend.services.search_service import search_and_download_agent_clips

        async def run_test():
            scenes = [
                PlanScene(
                    id=1,
                    description="开场",
                    keywords=["city"],
                    duration=6.0,
                    searchQuery="city motion",
                )
            ]

            with patch("backend.services.search_service.search_youtube") as mock_search, patch(
                "backend.services.search_service.download_video",
                new_callable=AsyncMock,
            ) as mock_download:
                mock_search.return_value = [
                    {
                        "id": "abc",
                        "title": "demo",
                        "url": "https://example.com/watch?v=abc",
                        "duration": 20.0,
                    }
                ]
                mock_download.return_value = "backend/downloads/demo.mp4"

                clips = await search_and_download_agent_clips("session-1", scenes)

            self.assertEqual(len(clips), 1)
            self.assertEqual(clips[0].sourceDuration, 20.0)
            self.assertAlmostEqual(clips[0].trimStart, 4.9)
            self.assertEqual(clips[0].trimDuration, 6.0)

        asyncio.run(run_test())


class ArtifactTrimMetadataTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", ConfirmFlowContractTests._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self.session_service = AgentSessionService(session_factory=self.session_factory)

    def tearDown(self):
        self.engine.dispose()

    def _create_queued_job(self) -> tuple[str, str]:
        from backend.services.agent_execution_service import AgentExecutionService

        session = self.session_service.create_session("做一个智能剪辑 agent 演示视频")
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )
        confirmed = execution_service.confirm_session(session.id)
        return session.id, confirmed.activeJobId

    def test_run_agent_job_persists_trim_metadata_in_artifacts(self):
        from backend.db.repositories import AgentArtifactRepository
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        async def fake_search_runner(_session_id, _scenes):
            return [
                {
                    "sceneId": 1,
                    "sourceUrl": "https://example.com/1",
                    "localPath": "backend/downloads/1.mp4",
                    "publicUrl": "/downloads/1.mp4",
                    "duration": 6.0,
                    "sourceDuration": 20.0,
                    "trimStart": 4.9,
                    "trimDuration": 6.0,
                }
            ]

        async def fake_render_runner(_session_id, _clips, _filename):
            return "/output/final.mp4"

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            fake_search_runner,
        ), patch(
            "backend.tasks.agent_tasks.render_video",
            fake_render_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            artifact_repo = AgentArtifactRepository(db)
            artifacts = artifact_repo.list_for_session(session_id)

        clip_artifact = next(row for row in artifacts if row.artifact_type == "clip")
        self.assertEqual(clip_artifact.metadata_json["sourceDuration"], 20.0)
        self.assertEqual(clip_artifact.metadata_json["trimStart"], 4.9)
        self.assertEqual(clip_artifact.metadata_json["trimDuration"], 6.0)


class RenderPreparationTests(unittest.TestCase):
    def test_prepare_render_clip_uses_trim_window_and_vertical_output(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import build_render_commands

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            sourceDuration=20.0,
            trimStart=4.9,
            trimDuration=6.0,
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")

        self.assertEqual(len(commands["segments"]), 1)
        self.assertIn("trimStart", commands["segments"][0])
        self.assertEqual(commands["segments"][0]["trimStart"], 4.9)
        self.assertEqual(commands["segments"][0]["trimDuration"], 6.0)
        self.assertEqual(commands["output"]["width"], 720)
        self.assertEqual(commands["output"]["height"], 1280)
        self.assertEqual(commands["output"]["fps"], 30)


class RenderBehaviorTests(unittest.TestCase):
    def test_render_video_uses_trim_duration_instead_of_full_source(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import build_render_commands

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            sourceDuration=120.0,
            trimStart=10.0,
            trimDuration=6.0,
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")

        self.assertNotEqual(commands["segments"][0]["trimDuration"], clip.sourceDuration)
        self.assertEqual(commands["segments"][0]["trimDuration"], 6.0)


class ConfirmFlowContractTests(unittest.TestCase):
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
        self.session_service = AgentSessionService(session_factory=self.session_factory)

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_execution_service_exposes_confirm_session(self):
        from backend.services.agent_execution_service import AgentExecutionService

        self.assertTrue(callable(getattr(AgentExecutionService, "confirm_session", None)))

    def test_confirm_session_queues_job_and_records_event(self):
        from backend.db.repositories import AgentEventRepository, AgentJobRepository
        from backend.models.agent import AgentStatus
        from backend.services.agent_execution_service import AgentExecutionService

        queued_job_ids: list[str] = []
        session = self.session_service.create_session("做一个智能剪辑演示视频")
        service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=queued_job_ids.append,
        )

        confirmed = service.confirm_session(session.id)

        self.assertEqual(confirmed.status, AgentStatus.QUEUED)
        self.assertEqual(confirmed.progress, 25)
        self.assertEqual(confirmed.currentStep, "任务已入队")
        self.assertIsNotNone(confirmed.activeJobId)
        self.assertEqual(queued_job_ids, [confirmed.activeJobId])
        self.assertEqual(len(confirmed.events), 1)
        self.assertEqual(confirmed.events[0].eventType, "job_queued")
        self.assertEqual(confirmed.events[0].message, "任务已入队，等待执行")

        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)

            job_record = job_repo.get(confirmed.activeJobId)
            self.assertIsNotNone(job_record)
            self.assertEqual(job_record.status, "queued")
            self.assertEqual(job_record.job_type, "generate_video")
            self.assertEqual(job_record.session_id, session.id)

            event_rows = event_repo.list_for_session(session.id)
            self.assertEqual(len(event_rows), 1)
            self.assertEqual(event_rows[0].job_id, confirmed.activeJobId)
            self.assertEqual(event_rows[0].event_type, "job_queued")

    def test_confirm_endpoint_returns_queued_session(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_execution_service import AgentExecutionService

        session = self.session_service.create_session("做一个品牌展示短片")
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )

        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                response = await client.post(f"/api/agent/sessions/{session.id}/confirm")
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["status"], AgentStatus.QUEUED.value)
                self.assertEqual(payload["currentStep"], "任务已入队")
                self.assertEqual(payload["progress"], 25)
                self.assertIsNotNone(payload["activeJobId"])

        with patch.object(agent_api_module, "execution_service", execution_service):
            asyncio.run(_run())


class AgentExecutionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", ConfirmFlowContractTests._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self.session_service = AgentSessionService(session_factory=self.session_factory)

    def tearDown(self):
        self.engine.dispose()

    def _create_queued_job(self) -> tuple[str, str]:
        from backend.services.agent_execution_service import AgentExecutionService

        session = self.session_service.create_session("做一个智能剪辑 agent 演示视频")
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )
        confirmed = execution_service.confirm_session(session.id)
        return session.id, confirmed.activeJobId

    def test_progress_service_exposes_required_methods(self):
        from backend.services.agent_progress_service import AgentProgressService

        self.assertTrue(callable(getattr(AgentProgressService, "record_event", None)))
        self.assertTrue(callable(getattr(AgentProgressService, "mark_job_running", None)))
        self.assertTrue(callable(getattr(AgentProgressService, "mark_job_failed", None)))
        self.assertTrue(callable(getattr(AgentProgressService, "mark_job_succeeded", None)))

    def test_run_agent_job_persists_success_state_events_and_artifacts(self):
        from backend.db.repositories import AgentArtifactRepository, AgentEventRepository, AgentJobRepository
        from backend.models.agent import AgentStatus
        from backend.services.agent_read_service import AgentReadService
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        async def fake_search_runner(_session_id, scenes):
            return [
                {
                    "sceneId": scene.id,
                    "sourceUrl": f"https://example.com/{scene.id}",
                    "localPath": f"backend/downloads/{scene.id}.mp4",
                    "publicUrl": f"/downloads/{scene.id}.mp4",
                    "duration": scene.duration,
                    "sourceDuration": scene.duration + 10,
                    "trimStart": 1.5,
                    "trimDuration": scene.duration,
                }
                for scene in scenes[:2]
            ]

        async def fake_render_runner(_session_id, clips, output_filename):
            self.assertEqual(len(clips), 2)
            self.assertTrue(output_filename.endswith(".mp4"))
            return "/output/final.mp4"

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            fake_search_runner,
        ), patch(
            "backend.tasks.agent_tasks.render_video",
            fake_render_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)
            artifact_repo = AgentArtifactRepository(db)

            job_record = job_repo.get(job_id)
            self.assertEqual(job_record.status, "succeeded")
            self.assertEqual(job_record.progress, 100)
            self.assertEqual(job_record.current_step, "完成")

            event_types = [row.event_type for row in event_repo.list_for_session(session_id)]
            self.assertEqual(
                event_types,
                ["job_queued", "job_started", "clips_ready", "render_started", "job_succeeded"],
            )

            artifacts = artifact_repo.list_for_session(session_id)
            self.assertEqual(len(artifacts), 3)
            self.assertEqual(artifacts[-1].artifact_type, "video")
            self.assertEqual(artifacts[-1].public_url, "/output/final.mp4")

        session = AgentReadService(session_factory=self.session_factory).read_session(session_id)
        self.assertEqual(session.status, AgentStatus.DONE)
        self.assertEqual(session.videoUrl, "/output/final.mp4")
        self.assertEqual(session.progress, 100)
        self.assertEqual(session.currentStep, "完成")
        self.assertEqual(len(session.clips), 2)
        self.assertEqual(session.clips[0].trimStart, 1.5)
        self.assertEqual(session.clips[0].trimDuration, session.clips[0].duration)
        self.assertGreater(session.clips[0].sourceDuration, session.clips[0].duration)
        self.assertEqual(session.events[-1].eventType, "job_succeeded")

    def test_run_agent_job_persists_failure_state(self):
        from backend.db.repositories import AgentEventRepository, AgentJobRepository
        from backend.models.agent import AgentStatus
        from backend.services.agent_read_service import AgentReadService
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        async def failing_search_runner(_session_id, _scenes):
            raise RuntimeError("素材检索失败")

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)

            job_record = job_repo.get(job_id)
            self.assertEqual(job_record.status, "failed")
            self.assertEqual(job_record.error_message, "素材检索失败")

            event_types = [row.event_type for row in event_repo.list_for_session(session_id)]
            self.assertEqual(event_types, ["job_queued", "job_started", "job_failed"])

        session = AgentReadService(session_factory=self.session_factory).read_session(session_id)
        self.assertEqual(session.status, AgentStatus.FAILED)
        self.assertEqual(session.error.message, "素材检索失败")
        self.assertEqual(session.currentStep, "处理失败：素材检索失败")


if __name__ == "__main__":
    unittest.main()
