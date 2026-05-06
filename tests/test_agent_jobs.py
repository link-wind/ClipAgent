import asyncio
import importlib
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base
from backend.services.agent_session_service import AgentSessionService


def _load_render_service():
    fake_ffmpeg = types.SimpleNamespace(Error=Exception)
    fake_websocket = types.ModuleType("backend.utils.websocket")
    fake_websocket.ws_manager = types.SimpleNamespace()
    services_pkg = importlib.import_module("backend.services")
    original_render_service = sys.modules.pop("backend.services.render_service", None)
    original_parent_render_service = getattr(services_pkg, "render_service", None)
    parent_had_render_service = hasattr(services_pkg, "render_service")
    try:
        with patch.dict(
            sys.modules,
            {
                "ffmpeg": fake_ffmpeg,
                "backend.utils.websocket": fake_websocket,
            },
        ):
            return importlib.import_module("backend.services.render_service")
    finally:
        sys.modules.pop("backend.services.render_service", None)
        if original_render_service is not None:
            sys.modules["backend.services.render_service"] = original_render_service
        if parent_had_render_service:
            services_pkg.render_service = original_parent_render_service
        elif hasattr(services_pkg, "render_service"):
            delattr(services_pkg, "render_service")


class _FakeStream:
    def __init__(self, label: str):
        self.label = label
        self.filters = []

    def filter(self, name, *args, **kwargs):
        self.filters.append((name, args, kwargs))
        return self


class _FakeInputNode:
    def __init__(self, has_audio: bool = True):
        self.video = _FakeStream("video")
        if has_audio:
            self.audio = _FakeStream("audio")


class _FakeOutputNode:
    def __init__(self):
        self.overwrite_called = False
        self.run_calls = []

    def overwrite_output(self):
        self.overwrite_called = True
        return self

    def run(self, **kwargs):
        self.run_calls.append(kwargs)
        return None


class _FakeCeleryApp:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.tasks = {}
        self.conf = types.SimpleNamespace()

    def task(self, *args, **kwargs):
        task_name = kwargs.get("name")

        def decorator(fn):
            self.tasks[task_name or fn.__name__] = fn
            return fn

        return decorator


if "celery" not in sys.modules:
    fake_celery_module = types.ModuleType("celery")
    fake_celery_module.Celery = _FakeCeleryApp
    sys.modules["celery"] = fake_celery_module


class CeleryContractTests(unittest.TestCase):
    def test_agent_task_entrypoint_exists(self):
        from backend.tasks.agent_tasks import run_agent_job

        self.assertTrue(callable(run_agent_job))

    def test_agent_tasks_import_propagates_celery_app_import_error(self):
        original_agent_tasks = sys.modules.pop("backend.tasks.agent_tasks", None)
        original_celery_app = sys.modules.pop("backend.tasks.celery_app", None)

        real_import = __import__

        def blocking_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "backend.tasks.celery_app":
                raise ModuleNotFoundError("mocked missing celery app module")
            return real_import(name, globals, locals, fromlist, level)

        try:
            with patch("builtins.__import__", side_effect=blocking_import):
                with self.assertRaisesRegex(ModuleNotFoundError, "mocked missing celery app module"):
                    importlib.import_module("backend.tasks.agent_tasks")
        finally:
            sys.modules.pop("backend.tasks.agent_tasks", None)
            if original_agent_tasks is not None:
                sys.modules["backend.tasks.agent_tasks"] = original_agent_tasks
            if original_celery_app is not None:
                sys.modules["backend.tasks.celery_app"] = original_celery_app

    def test_celery_app_subprocess_registers_agent_job_task(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import sys, types\n"
                    "m = types.ModuleType('celery')\n"
                    "class FakeCelery:\n"
                    "    def __init__(self, *args, **kwargs):\n"
                    "        self.tasks = {}\n"
                    "        self.conf = types.SimpleNamespace()\n"
                    "    def task(self, *args, **kwargs):\n"
                    "        name = kwargs.get('name')\n"
                    "        def decorator(fn):\n"
                    "            self.tasks[name or fn.__name__] = fn\n"
                    "            return fn\n"
                    "        return decorator\n"
                    "m.Celery = FakeCelery\n"
                    "sys.modules['celery'] = m\n"
                    "from backend.tasks.celery_app import celery_app\n"
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

    def test_celery_settings_support_default_and_override_queue(self):
        from backend.config import get_settings

        get_settings.cache_clear()
        try:
            default_settings = get_settings()
            self.assertEqual(default_settings.celery_queue, "clipforge-agent")

            with patch.dict("os.environ", {"CLIPFORGE_CELERY_QUEUE": "clipforge-agent-wt1"}, clear=False):
                get_settings.cache_clear()
                override_settings = get_settings()
                self.assertEqual(override_settings.celery_queue, "clipforge-agent-wt1")
        finally:
            get_settings.cache_clear()

    def test_celery_app_uses_configured_queue_name(self):
        import backend.tasks.celery_app as celery_app_module

        with patch.dict("os.environ", {"CLIPFORGE_CELERY_QUEUE": "clipforge-agent-wt2"}, clear=False):
            original_module = sys.modules.pop("backend.tasks.celery_app", None)
            original_config = sys.modules.pop("backend.config", None)
            try:
                reloaded_module = importlib.import_module("backend.tasks.celery_app")
                self.assertEqual(reloaded_module.celery_app.conf.task_default_queue, "clipforge-agent-wt2")
            finally:
                sys.modules.pop("backend.tasks.celery_app", None)
                sys.modules.pop("backend.config", None)
                if original_config is not None:
                    sys.modules["backend.config"] = original_config
                if original_module is not None:
                    sys.modules["backend.tasks.celery_app"] = original_module
                importlib.reload(celery_app_module)


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

    def test_clip_info_supports_caption(self):
        from backend.models.agent import ClipInfo

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/video",
            localPath="backend/downloads/demo.mp4",
            publicUrl="/downloads/demo.mp4",
            duration=6.0,
            caption="开场镜头",
        )

        self.assertEqual(clip.caption, "开场镜头")


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
        from backend.services.asset_providers.types import AssetCandidate
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

            with patch("backend.services.search_service.search_youtube_candidates") as mock_search, patch(
                "backend.services.search_service.download_video",
                new_callable=AsyncMock,
            ) as mock_download:
                mock_search.return_value = [
                    AssetCandidate(
                        provider="youtube",
                        id="abc",
                        title="demo",
                        source_url="https://example.com/watch?v=abc",
                        download_url="https://example.com/watch?v=abc",
                        duration=20.0,
                    )
                ]
                mock_download.return_value = "backend/downloads/demo.mp4"

                clips = await search_and_download_agent_clips("session-1", scenes)

            self.assertEqual(len(clips), 1)
            self.assertEqual(clips[0].sourceDuration, 20.0)
            self.assertAlmostEqual(clips[0].trimStart, 4.9)
            self.assertEqual(clips[0].trimDuration, 6.0)

        asyncio.run(run_test())

    def test_search_and_download_agent_clips_populates_caption(self):
        from backend.models.agent import PlanScene
        from backend.services.asset_providers.types import AssetCandidate
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

            with patch("backend.services.search_service.search_youtube_candidates") as mock_search, patch(
                "backend.services.search_service.download_video",
                new_callable=AsyncMock,
            ) as mock_download:
                mock_search.return_value = [
                    AssetCandidate(
                        provider="youtube",
                        id="abc",
                        title="demo",
                        source_url="https://example.com/watch?v=abc",
                        download_url="https://example.com/watch?v=abc",
                        duration=20.0,
                    )
                ]
                mock_download.return_value = "backend/downloads/demo.mp4"

                clips = await search_and_download_agent_clips("session-1", scenes)

            self.assertEqual(len(clips), 1)
            self.assertEqual(clips[0].caption, "开场")

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

    def test_run_agent_job_persists_caption_in_artifacts(self):
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
                    "caption": "开场镜头",
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
        self.assertEqual(clip_artifact.metadata_json["caption"], "开场镜头")

    def test_run_agent_job_persists_provider_metadata_in_artifacts(self):
        from backend.db.repositories import AgentArtifactRepository
        from backend.services.asset_providers.metadata import remember_clip_metadata
        from backend.tasks.agent_tasks import run_agent_job

        session_id, job_id = self._create_queued_job()

        async def fake_search_runner(_session_id, _scenes):
            local_path = "backend/downloads/1.mp4"
            remember_clip_metadata(
                local_path,
                {
                    "provider": "pexels",
                    "providerId": "asset-42",
                    "author": "Pexels Creator",
                    "sourceUrl": "https://www.pexels.com/video/asset-42/",
                    "downloadUrl": "https://videos.pexels.com/asset-42.mp4",
                    "width": 1920,
                    "height": 1080,
                },
            )
            return [
                {
                    "sceneId": 1,
                    "sourceUrl": "https://example.com/1",
                    "localPath": local_path,
                    "publicUrl": "/downloads/1.mp4",
                    "duration": 6.0,
                    "caption": "开场镜头",
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
        self.assertEqual(clip_artifact.metadata_json["provider"], "pexels")
        self.assertEqual(clip_artifact.metadata_json["providerId"], "asset-42")
        self.assertEqual(clip_artifact.metadata_json["author"], "Pexels Creator")
        self.assertEqual(
            clip_artifact.metadata_json["sourceUrl"],
            "https://www.pexels.com/video/asset-42/",
        )
        self.assertEqual(
            clip_artifact.metadata_json["downloadUrl"],
            "https://videos.pexels.com/asset-42.mp4",
        )
        self.assertEqual(clip_artifact.metadata_json["width"], 1920)
        self.assertEqual(clip_artifact.metadata_json["height"], 1080)
        self.assertEqual(clip_artifact.metadata_json["caption"], "开场镜头")
        self.assertEqual(clip_artifact.metadata_json["sourceDuration"], 20.0)
        self.assertEqual(clip_artifact.metadata_json["trimStart"], 4.9)
        self.assertEqual(clip_artifact.metadata_json["trimDuration"], 6.0)


class RenderPreparationTests(unittest.TestCase):
    def test_default_bgm_asset_exists(self):
        render_service = _load_render_service()

        self.assertTrue(Path(render_service.BGM_PATH).is_file())

    def test_prepare_render_clip_uses_trim_window_and_vertical_output(self):
        from backend.models.agent import ClipInfo
        build_render_commands = _load_render_service().build_render_commands

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

    def test_prepare_render_clip_includes_caption_and_bgm_metadata(self):
        from backend.models.agent import ClipInfo
        build_render_commands = _load_render_service().build_render_commands

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            caption="开场建立氛围",
            sourceDuration=20.0,
            trimStart=4.9,
            trimDuration=6.0,
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")

        self.assertEqual(commands["segments"][0]["caption"], "开场建立氛围")
        self.assertIn("bgm", commands)
        self.assertTrue(commands["bgm"]["path"].endswith("default_bgm.mp3"))
        self.assertEqual(commands["bgm"]["volume"], 0.18)

    def test_prepare_render_clip_normalizes_missing_caption_to_empty_string(self):
        from backend.models.task import ClipInfo
        build_render_commands = _load_render_service().build_render_commands

        clip = ClipInfo(
            sceneId=1,
            videoUrl="backend/downloads/legacy.mp4",
            startTime=0.0,
            duration=6.0,
        )

        commands = build_render_commands([clip], "backend/output/final.mp4")

        self.assertEqual(commands["segments"][0]["caption"], "")


class RenderBehaviorTests(unittest.TestCase):
    def test_clip_caption_helper_returns_string_for_none(self):
        render_service = _load_render_service()

        clip = types.SimpleNamespace(caption=None)

        self.assertEqual(render_service._clip_caption(clip), "")

    def test_resolve_caption_font_prefers_env_override(self):
        render_service = _load_render_service()

        with tempfile.TemporaryDirectory() as temp_dir:
            font_path = Path(temp_dir) / "custom-caption.ttf"
            font_path.write_text("font", encoding="utf-8")

            with patch.dict(render_service.os.environ, {"CLIPFORGE_CAPTION_FONT": str(font_path)}, clear=False):
                self.assertEqual(render_service._resolve_caption_font(), str(font_path))

    def test_resolve_caption_font_supports_linux_candidates(self):
        render_service = _load_render_service()

        linux_font = Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc")
        checked_candidates = []

        def fake_exists(path_obj):
            checked_candidates.append(str(path_obj))
            return path_obj == linux_font

        with patch.dict(render_service.os.environ, {}, clear=True), patch(
            "pathlib.Path.exists",
            autospec=True,
            side_effect=fake_exists,
        ):
            resolved = render_service._resolve_caption_font()

        self.assertEqual(resolved, str(linux_font))
        self.assertTrue(
            any("usr" in candidate and "share" in candidate and "fonts" in candidate for candidate in checked_candidates)
        )

    def test_render_shortform_video_consumes_caption_and_bgm_settings(self):
        from backend.models.agent import ClipInfo

        render_service = _load_render_service()
        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            caption="片头字幕",
            sourceDuration=20.0,
            trimStart=4.9,
            trimDuration=6.0,
        )

        captured_segments = []

        def fake_render_segment(segment, segment_path):
            captured_segments.append((segment, segment_path))

        with patch.object(render_service, "_render_segment", side_effect=fake_render_segment), patch.object(
            render_service,
            "_concat_segments",
        ) as concat_mock, patch.object(
            render_service,
            "_mix_background_music",
            create=True,
        ) as mix_mock:
            video_url = render_service.render_shortform_video([clip], "final.mp4")

        self.assertEqual(video_url, "/output/final.mp4")
        self.assertEqual(len(captured_segments), 1)
        self.assertEqual(captured_segments[0][0]["caption"], "片头字幕")
        concat_mock.assert_called_once()
        mix_mock.assert_called_once()
        self.assertEqual(mix_mock.call_args.args[2]["volume"], 0.18)

    def test_render_shortform_video_reports_captioning_and_audio_mix_at_real_nodes(self):
        from backend.models.agent import ClipInfo

        render_service = _load_render_service()
        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/1",
            localPath="backend/downloads/1.mp4",
            publicUrl="/downloads/1.mp4",
            duration=6.0,
            caption="片头字幕",
            sourceDuration=20.0,
            trimStart=4.9,
            trimDuration=6.0,
        )

        observed_events = []
        call_sequence = []

        def fake_progress_callback(event_type, message, progress):
            observed_events.append((event_type, message, progress))
            call_sequence.append(f"callback:{event_type}")

        def fake_render_segment(segment, segment_path):
            self.assertEqual(observed_events, [("render_captioning", "正在合成字幕", 82)])
            call_sequence.append("render_segment")

        def fake_concat_segments(_segment_paths, _output_path):
            call_sequence.append("concat_segments")

        def fake_mix_background_music(_input_path, _output_path, _bgm):
            self.assertEqual(
                observed_events,
                [
                    ("render_captioning", "正在合成字幕", 82),
                    ("render_audio_mix", "正在混合背景音乐", 88),
                ],
            )
            call_sequence.append("mix_background_music")

        with patch.object(render_service, "_render_segment", side_effect=fake_render_segment), patch.object(
            render_service,
            "_concat_segments",
            side_effect=fake_concat_segments,
        ), patch.object(
            render_service,
            "_mix_background_music",
            side_effect=fake_mix_background_music,
        ):
            render_service.render_shortform_video([clip], "final.mp4", progress_callback=fake_progress_callback)

        self.assertEqual(
            call_sequence,
            [
                "callback:render_captioning",
                "render_segment",
                "concat_segments",
                "callback:render_audio_mix",
                "mix_background_music",
            ],
        )

    def test_render_video_uses_trim_duration_instead_of_full_source(self):
        from backend.models.agent import ClipInfo
        build_render_commands = _load_render_service().build_render_commands

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

    def test_render_segment_uses_silence_track_when_source_has_no_audio(self):
        render_service = _load_render_service()
        input_node = _FakeInputNode(has_audio=False)
        silent_node = _FakeInputNode(has_audio=True)
        output_node = _FakeOutputNode()

        def fake_input(path, **kwargs):
            if path == "demo.mp4":
                return input_node
            if path == "anullsrc=channel_layout=stereo:sample_rate=44100":
                self.assertEqual(kwargs["f"], "lavfi")
                self.assertEqual(kwargs["t"], 3.0)
                return silent_node
            raise AssertionError(f"unexpected input: {path}")

        with patch.object(render_service.os.path, "exists", return_value=True), patch.object(
            render_service,
            "_input_has_audio",
            return_value=False,
        ), patch.object(
            render_service.ffmpeg,
            "probe",
            return_value={"format": {"duration": "12.5"}},
            create=True,
        ), patch.object(render_service.ffmpeg, "input", side_effect=fake_input, create=True), patch.object(
            render_service.ffmpeg,
            "output",
            return_value=output_node,
            create=True,
        ):
            render_service._render_segment(
                {
                    "input": "demo.mp4",
                    "trimStart": 1.0,
                    "trimDuration": 3.0,
                    "caption": "",
                },
                "segment.mp4",
            )

        self.assertTrue(output_node.overwrite_called)
        self.assertEqual(output_node.run_calls, [{"capture_stdout": True, "capture_stderr": True}])
        self.assertIn(("aresample", (44100,), {}), silent_node.audio.filters)

    def test_mix_background_music_uses_bgm_only_when_base_video_has_no_audio(self):
        render_service = _load_render_service()
        base_node = _FakeInputNode(has_audio=False)
        bgm_node = _FakeInputNode(has_audio=True)
        output_node = _FakeOutputNode()

        def fake_input(path, **kwargs):
            if path == "concat.mp4":
                return base_node
            if path == "bgm.mp3":
                self.assertEqual(kwargs["stream_loop"], -1)
                return bgm_node
            raise AssertionError(f"unexpected input: {path}")

        with patch.object(render_service.os.path, "exists", return_value=True), patch.object(
            render_service,
            "_input_has_audio",
            return_value=False,
        ), patch.object(
            render_service.ffmpeg,
            "probe",
            return_value={"format": {"duration": "12.5"}},
            create=True,
        ), patch.object(render_service.ffmpeg, "input", side_effect=fake_input, create=True), patch.object(
            render_service.ffmpeg,
            "output",
            return_value=output_node,
            create=True,
        ), patch.object(render_service.ffmpeg, "filter", create=True) as filter_mock:
            render_service._mix_background_music(
                "concat.mp4",
                "final.mp4",
                {"path": "bgm.mp3", "volume": 0.3},
            )

        filter_mock.assert_not_called()
        self.assertTrue(output_node.overwrite_called)
        self.assertEqual(output_node.run_calls, [{"capture_stdout": True, "capture_stderr": True}])
        self.assertIn(("volume", (0.3,), {}), bgm_node.audio.filters)
        self.assertIn(("atrim", (), {"duration": 12.5}), bgm_node.audio.filters)

    def test_apply_caption_skips_drawtext_when_no_font_available(self):
        render_service = _load_render_service()
        video_stream = _FakeStream("video")
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_path = str(Path(temp_dir) / "segment.mp4")

            with patch.object(render_service, "_resolve_caption_font", return_value=None):
                output_stream, caption_path = render_service._apply_caption(
                    video_stream,
                    "需要显示的字幕",
                    segment_path,
                )

            self.assertIs(output_stream, video_stream)
            self.assertIsNone(caption_path)
            self.assertEqual(video_stream.filters, [])
            self.assertFalse(Path(segment_path).with_suffix(".caption.txt").exists())

    def test_apply_caption_uses_drawtext_when_font_available(self):
        render_service = _load_render_service()
        video_stream = _FakeStream("video")
        with tempfile.TemporaryDirectory() as temp_dir:
            segment_path = str(Path(temp_dir) / "segment.mp4")
            caption_file = Path(segment_path).with_suffix(".caption.txt")

            with patch.object(render_service, "_resolve_caption_font", return_value="C:/Fonts/test.ttf"):
                output_stream, caption_path = render_service._apply_caption(
                    video_stream,
                    "需要显示的字幕",
                    segment_path,
                )

            self.assertIs(output_stream, video_stream)
            self.assertEqual(caption_path, caption_file)
            self.assertEqual(len(video_stream.filters), 1)
            self.assertEqual(video_stream.filters[0][0], "drawtext")
            self.assertEqual(video_stream.filters[0][2]["fontfile"], "C:/Fonts/test.ttf")
            self.assertTrue(caption_file.exists())


class RenderServiceImportIsolationTests(unittest.TestCase):
    def test_load_render_service_restores_parent_package_reference(self):
        import backend.services as services_pkg

        original_render_service = types.ModuleType("backend.services.render_service")
        original_render_service.marker = "original"
        original_parent_value = getattr(services_pkg, "render_service", None)
        parent_had_render_service = hasattr(services_pkg, "render_service")
        sys.modules["backend.services.render_service"] = original_render_service
        services_pkg.render_service = original_render_service

        try:
            loaded = _load_render_service()
            self.assertIsNot(loaded, original_render_service)
            self.assertIs(sys.modules["backend.services.render_service"], original_render_service)
            self.assertIs(services_pkg.render_service, original_render_service)
        finally:
            if parent_had_render_service:
                services_pkg.render_service = original_parent_value
            elif hasattr(services_pkg, "render_service"):
                delattr(services_pkg, "render_service")
            sys.modules["backend.services.render_service"] = original_render_service


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
        import backend.api.agent as agent_api_module
        from backend.main import app
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
                    "caption": f"场景{scene.id}字幕",
                    "sourceDuration": scene.duration + 10,
                    "trimStart": 1.5,
                    "trimDuration": scene.duration,
                }
                for scene in scenes[:2]
            ]

        async def fake_render_runner(_session_id, clips, output_filename, progress_callback=None):
            self.assertEqual(len(clips), 2)
            self.assertTrue(output_filename.endswith(".mp4"))
            self.assertIsNotNone(progress_callback)
            progress_callback("render_captioning", "正在合成字幕", 82)
            progress_callback("render_audio_mix", "正在混合背景音乐", 88)
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

            event_rows = event_repo.list_for_session(session_id)
            event_types = [row.event_type for row in event_rows]
            self.assertEqual(
                event_types,
                [
                    "job_queued",
                    "job_started",
                    "clips_ready",
                    "render_started",
                    "render_captioning",
                    "render_audio_mix",
                    "job_succeeded",
                ],
            )
            captioning_events = [row for row in event_rows if row.event_type == "render_captioning"]
            audio_mix_events = [row for row in event_rows if row.event_type == "render_audio_mix"]
            self.assertEqual(len(captioning_events), 1)
            self.assertEqual(len(audio_mix_events), 1)
            self.assertEqual(captioning_events[0].message, "正在合成字幕")
            self.assertEqual(captioning_events[0].progress, 82)
            self.assertEqual(audio_mix_events[0].message, "正在混合背景音乐")
            self.assertEqual(audio_mix_events[0].progress, 88)

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
        self.assertEqual(session.clips[0].caption, "场景1字幕")
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

    def test_run_agent_job_persists_failure_state_when_render_service_import_fails(self):
        from backend.db.repositories import AgentEventRepository, AgentJobRepository
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
                }
                for scene in scenes[:1]
            ]

        real_import = __import__

        def blocking_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "backend.services.render_service":
                raise ModuleNotFoundError("mocked missing render dependency")
            return real_import(name, globals, locals, fromlist, level)

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            fake_search_runner,
        ), patch("backend.tasks.agent_tasks.render_video", None), patch(
            "builtins.__import__",
            side_effect=blocking_import,
        ):
            run_agent_job(job_id)

        with self.session_factory() as db:
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)

            job_record = job_repo.get(job_id)
            self.assertEqual(job_record.status, "failed")
            self.assertEqual(job_record.error_message, "mocked missing render dependency")

            event_types = [row.event_type for row in event_repo.list_for_session(session_id)]
            self.assertEqual(
                event_types,
                ["job_queued", "job_started", "clips_ready", "render_started", "job_failed"],
            )

        session = AgentReadService(session_factory=self.session_factory).read_session(session_id)
        self.assertEqual(session.status, AgentStatus.FAILED)
        self.assertEqual(session.error.message, "mocked missing render dependency")
        self.assertEqual(session.currentStep, "处理失败：mocked missing render dependency")


class FrontendPolishContractTests(unittest.TestCase):
    def test_result_panel_references_clip_metadata_fields(self):
        source = Path("src/components/agent/ResultPanel.tsx").read_text(encoding="utf-8")

        self.assertIn("caption", source)
        self.assertIn("trimStart", source)
        self.assertIn("trimDuration", source)
        self.assertIn("sourceDuration", source)

    def test_progress_panel_contains_render_progress_messages(self):
        source = Path("src/components/agent/ProgressPanel.tsx").read_text(encoding="utf-8")

        self.assertIn("正在合成字幕", source)
        self.assertIn("正在混合背景音乐", source)


if __name__ == "__main__":
    unittest.main()
