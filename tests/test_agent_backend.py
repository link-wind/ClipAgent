import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_test_client(app):
    from fastapi.testclient import TestClient

    original_init = httpx.Client.__init__

    def compatible_init(self, *args, **kwargs):
        # 兼容新版 httpx 移除 app 参数后旧版 TestClient 的调用方式
        kwargs.pop("app", None)
        return original_init(self, *args, **kwargs)

    httpx.Client.__init__ = compatible_init
    try:
        return TestClient(app)
    finally:
        httpx.Client.__init__ = original_init


class BackendImportTests(unittest.TestCase):
    def test_backend_main_imports_without_model_name_errors(self):
        module = importlib.import_module("backend.main")
        self.assertTrue(hasattr(module, "app"))

    def test_uvicorn_style_backend_main_imports(self):
        module = importlib.import_module("backend.main")
        self.assertEqual(module.app.title, "ClipForge API")

    def test_gpt_service_requires_api_key_when_analyzing(self):
        from backend.services.gpt_service import GPTService

        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            service = GPTService()
            with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY is not configured"):
                asyncio.run(service.analyze_script("测试脚本"))


class AgentSessionTests(unittest.TestCase):
    def test_create_session_starts_idle_with_empty_messages(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()

        self.assertEqual(session.status, AgentStatus.IDLE)
        self.assertEqual(session.messages, [])
        self.assertIsNone(session.plan)

    def test_create_session_with_prompt_generates_plan_ready_session(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个 30 秒科技产品短视频")

        self.assertEqual(session.status, AgentStatus.PLAN_READY)
        self.assertEqual(session.messages[0].role, "user")
        self.assertIsNotNone(session.plan)
        self.assertGreater(len(session.plan.scenes), 0)

    def test_add_user_message_to_empty_session_generates_plan(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()

        updated = service.add_user_message(session.id, "剪一个科技发布会预热视频")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNotNone(updated.plan)
        self.assertEqual(updated.messages[0].role, "user")
        self.assertEqual(updated.messages[1].role, "assistant")

    def test_add_user_message_to_plan_ready_session_appends_messages(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个 30 秒科技产品短视频")
        original_message_count = len(session.messages)

        updated = service.add_user_message(session.id, "改成更有未来感")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertEqual(len(updated.messages), original_message_count + 2)
        self.assertEqual(updated.messages[-2].role, "user")
        self.assertEqual(updated.messages[-1].role, "assistant")

    def test_add_user_message_rejects_non_editable_session_status(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个 30 秒科技产品短视频")
        session.status = AgentStatus.RENDERING

        with self.assertRaisesRegex(RuntimeError, "Session is not editable while rendering"):
            service.add_user_message(session.id, "现在不要渲染")

        self.assertEqual(session.status, AgentStatus.RENDERING)

    def test_add_user_message_rejects_blank_content(self):
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()

        with self.assertRaisesRegex(ValueError, "Message content is required"):
            service.add_user_message(session.id, "   ")


class AgentApiTests(unittest.TestCase):
    def test_create_session_api_returns_plan_ready_session(self):
        from backend.main import app

        client = _make_test_client(app)
        response = client.post("/api/agent/sessions", json={"message": "做一个科技短片"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertIn("plan", data)
        self.assertGreater(len(data["plan"]["scenes"]), 0)

    def test_add_message_updates_existing_session(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        response = client.post(
            f"/api/agent/sessions/{created['id']}/messages",
            json={"message": "更商务一点"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertGreaterEqual(len(data["messages"]), 3)

    def test_get_missing_session_returns_404(self):
        from backend.main import app

        client = _make_test_client(app)
        response = client.get("/api/agent/sessions/missing")

        self.assertEqual(response.status_code, 404)

    def test_add_message_to_missing_session_returns_404(self):
        from backend.main import app

        client = _make_test_client(app)
        response = client.post(
            "/api/agent/sessions/missing/messages",
            json={"message": "更商务一点"},
        )

        self.assertEqual(response.status_code, 404)

    def test_add_blank_message_returns_400(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        response = client.post(
            f"/api/agent/sessions/{created['id']}/messages",
            json={"message": "   "},
        )

        self.assertEqual(response.status_code, 400)

    def test_get_session_returns_created_session(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        response = client.get(f"/api/agent/sessions/{created['id']}")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["id"], created["id"])
        self.assertEqual(data["status"], created["status"])


class AgentExecutionContractTests(unittest.TestCase):
    def test_clip_info_contains_local_and_public_paths(self):
        from backend.models.agent import ClipInfo

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/watch?v=1",
            localPath="D:/Code/ClipForge_v2/backend/downloads/example.mp4",
            publicUrl="/downloads/example.mp4",
            startTime=0,
            duration=6,
        )

        self.assertTrue(clip.localPath.endswith("example.mp4"))
        self.assertEqual(clip.publicUrl, "/downloads/example.mp4")

    def test_render_uses_local_path_inputs(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import build_render_inputs

        clips = [
            ClipInfo(
                sceneId=1,
                sourceUrl="https://example.com/source",
                localPath="backend/downloads/a.mp4",
                publicUrl="/downloads/a.mp4",
                duration=6,
            )
        ]

        self.assertEqual(build_render_inputs(clips), ["backend/downloads/a.mp4"])

    def test_render_helper_keeps_legacy_task_video_url_inputs(self):
        from backend.models.task import ClipInfo
        from backend.services.render_service import build_render_inputs

        clips = [
            ClipInfo(
                sceneId=1,
                videoUrl="/downloads/legacy.mp4",
                startTime=0,
                duration=6,
            )
        ]

        self.assertEqual(build_render_inputs(clips), ["/downloads/legacy.mp4"])

    def test_concat_agent_clip_uses_local_path_as_ffmpeg_input(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import concat_clips_simple

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/source.mp4",
            localPath="backend/downloads/agent.mp4",
            publicUrl="/downloads/agent.mp4",
            duration=6,
        )

        with patch("backend.services.render_service.ffmpeg.input") as mock_input:
            with patch("backend.services.render_service.ffmpeg.output") as mock_output:
                mock_output.return_value.run.return_value = None

                result = concat_clips_simple([clip], "out.mp4")

        mock_input.assert_called_once_with("backend/downloads/agent.mp4")
        self.assertEqual(result, "/output/out.mp4")

    def test_confirm_session_with_plan_starts_searching(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个科技短片")

        updated = service.confirm_session(session.id)

        self.assertEqual(updated.status, AgentStatus.SEARCHING)
        self.assertEqual(updated.progress, 30)
        self.assertIn("正在搜索素材", updated.currentStep)

    def test_confirm_session_rejects_searching_without_resetting_status(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个科技短片")
        session.status = AgentStatus.SEARCHING
        session.progress = 45
        session.currentStep = "正在下载素材"

        with self.assertRaisesRegex(RuntimeError, "Session cannot be confirmed while searching"):
            service.confirm_session(session.id)

        self.assertEqual(session.status, AgentStatus.SEARCHING)
        self.assertEqual(session.progress, 45)
        self.assertEqual(session.currentStep, "正在下载素材")

    def test_confirm_session_rejects_rendering_without_resetting_status(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个科技短片")
        session.status = AgentStatus.RENDERING
        session.progress = 70
        session.currentStep = "正在合成视频"

        with self.assertRaisesRegex(RuntimeError, "Session cannot be confirmed while rendering"):
            service.confirm_session(session.id)

        self.assertEqual(session.status, AgentStatus.RENDERING)
        self.assertEqual(session.progress, 70)
        self.assertEqual(session.currentStep, "正在合成视频")

    def test_confirm_session_without_plan_fails_with_planning_error(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()

        updated = service.confirm_session(session.id)

        self.assertEqual(updated.status, AgentStatus.FAILED)
        self.assertIsNotNone(updated.error)
        self.assertEqual(updated.error.retryableStep, "planning")

    def test_failed_planning_session_accepts_message_and_recovers_plan(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()
        service.confirm_session(session.id)

        updated = service.add_user_message(session.id, "重新生成科技短片方案")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNotNone(updated.plan)
        self.assertIsNone(updated.error)

    def test_failed_planning_session_with_existing_plan_regenerates_plan(self):
        from backend.models.agent import AgentError, AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个科技短片")
        original_message_count = len(session.messages)
        session.status = AgentStatus.FAILED
        session.error = AgentError(message="规划失败", retryableStep="planning")

        updated = service.add_user_message(session.id, "重新规划但保留标题")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNone(updated.error)
        self.assertIsNotNone(updated.plan)
        self.assertEqual(updated.plan.title, "智能剪辑短片")
        self.assertEqual(len(updated.messages), original_message_count + 2)
        self.assertEqual(updated.messages[-2].role, "user")
        self.assertEqual(updated.messages[-1].role, "assistant")

    def test_agent_search_download_returns_agent_clip_paths(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scene = PlanScene(
            id=7,
            description="展示产品细节",
            keywords=["product", "detail"],
            duration=5,
            searchQuery="product detail",
        )

        with patch("backend.services.search_service.search_youtube") as mock_search:
            with patch("backend.services.search_service.download_video") as mock_download:
                mock_search.return_value = [
                    {
                        "id": "abc123",
                        "title": "Product detail",
                        "url": "https://www.youtube.com/watch?v=abc123",
                        "duration": 12,
                    }
                ]
                mock_download.return_value = "backend/downloads/session_7.mp4"

                clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sceneId, 7)
        self.assertEqual(clips[0].sourceUrl, "https://www.youtube.com/watch?v=abc123")
        self.assertEqual(clips[0].localPath, "backend/downloads/session_7.mp4")
        self.assertEqual(clips[0].publicUrl, "/downloads/session_7.mp4")

    def test_agent_download_tries_next_search_result_after_youtube_failure(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )

        with patch("backend.services.search_service.search_youtube") as mock_search:
            with patch("backend.services.search_service.download_video") as mock_download:
                mock_search.return_value = [
                    {"id": "bad", "title": "Bad", "url": "https://www.youtube.com/watch?v=bad", "duration": 12},
                    {"id": "good", "title": "Good", "url": "https://www.youtube.com/watch?v=good", "duration": 14},
                ]
                mock_download.side_effect = [
                    Exception("YouTube said: ERROR - Precondition check failed."),
                    "backend/downloads/session_3.mp4",
                ]

                clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(mock_download.call_count, 2)
        self.assertEqual(clips[0].sourceUrl, "https://www.youtube.com/watch?v=good")

    def test_youtube_options_use_current_clients_and_retry_settings(self):
        from backend.services.search_service import build_download_options, build_search_options

        search_options = build_search_options()
        download_options = build_download_options("backend/downloads/example.mp4", [])

        self.assertIn("extractor_args", search_options)
        self.assertIn("youtube", search_options["extractor_args"])
        self.assertIn("player_client", search_options["extractor_args"]["youtube"])
        self.assertGreaterEqual(download_options["retries"], 3)
        self.assertIn("bestvideo", download_options["format"])

    def test_youtube_options_avoid_po_token_clients_and_enable_node_ejs(self):
        from backend.services.search_service import build_download_options, build_search_options

        search_options = build_search_options()
        download_options = build_download_options("backend/downloads/example.mp4", [])

        self.assertEqual(search_options["extractor_args"]["youtube"]["player_client"], ["web"])
        self.assertEqual(download_options["extractor_args"]["youtube"]["player_client"], ["web"])
        self.assertEqual(download_options["js_runtimes"], {"node": {}})
        self.assertIn("ejs:npm", download_options["remote_components"])

    def test_summarize_youtube_download_errors_for_agent_status(self):
        from backend.services.search_service import summarize_download_error

        message = summarize_download_error(
            "ios client hls formats require a GVS PO Token. Only images are available. "
            "Requested format is not available."
        )

        self.assertIn("YouTube 当前没有返回可下载视频格式", message)
        self.assertIn("PO Token", message)


class FrontendProxyConfigTests(unittest.TestCase):
    def test_next_rewrites_include_agent_api_and_static_media(self):
        import json
        import subprocess

        command = [
            "node",
            "-e",
            (
                "const config = require('./next.config.js');"
                "Promise.resolve(config.rewrites()).then((value) => console.log(JSON.stringify(value)));"
            ),
        ]
        result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, check=True)
        rewrites = json.loads(result.stdout)

        self.assertIn(
            {"source": "/api/agent/:path*", "destination": "http://127.0.0.1:8010/api/agent/:path*"},
            rewrites,
        )
        self.assertIn(
            {"source": "/output/:path*", "destination": "http://127.0.0.1:8010/output/:path*"},
            rewrites,
        )
        self.assertIn(
            {"source": "/downloads/:path*", "destination": "http://127.0.0.1:8010/downloads/:path*"},
            rewrites,
        )


class FrontendClientContractTests(unittest.TestCase):
    def test_agent_chat_resets_stale_session_on_missing_backend_session(self):
        content = (ROOT / "src" / "components" / "agent" / "AgentChat.tsx").read_text(encoding="utf-8")

        self.assertIn("会话已失效", content)
        self.assertIn("setSession(null)", content)

    def test_run_confirmed_session_completes_with_clips_and_video_url(self):
        from backend.models.agent import AgentStatus, ClipInfo
        from backend.services.agent_service import AgentService

        async def fake_search(session_id, scenes):
            return [
                ClipInfo(
                    sceneId=scenes[0].id,
                    sourceUrl="https://example.com/source.mp4",
                    localPath="backend/downloads/source.mp4",
                    publicUrl="/downloads/source.mp4",
                    duration=6,
                )
            ]

        async def fake_render(session_id, clips, output_filename):
            return f"/output/{output_filename}"

        service = AgentService()
        session = service.create_session("做一个科技短片")
        service.confirm_session(session.id)

        updated = asyncio.run(service.run_confirmed_session(session.id, fake_search, fake_render))

        self.assertEqual(updated.status, AgentStatus.DONE)
        self.assertEqual(updated.progress, 100)
        self.assertEqual(len(updated.clips), 1)
        self.assertEqual(updated.videoUrl, f"/output/{session.id}.mp4")

    def test_run_confirmed_session_without_downloaded_clips_fails(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        async def fake_search(session_id, scenes):
            return []

        async def fake_render(session_id, clips, output_filename):
            return f"/output/{output_filename}"

        service = AgentService()
        session = service.create_session("做一个科技短片")
        service.confirm_session(session.id)

        updated = asyncio.run(service.run_confirmed_session(session.id, fake_search, fake_render))

        self.assertEqual(updated.status, AgentStatus.FAILED)
        self.assertIsNotNone(updated.error)
        self.assertEqual(updated.error.retryableStep, "searching")

    def test_confirm_missing_session_returns_404(self):
        from backend.main import app

        client = _make_test_client(app)
        response = client.post("/api/agent/sessions/missing/confirm")

        self.assertEqual(response.status_code, 404)

    def test_confirm_session_api_with_plan_starts_searching(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        with patch("backend.api.agent.agent_service.run_confirmed_session", new_callable=AsyncMock) as mock_run:
            response = client.post(f"/api/agent/sessions/{created['id']}/confirm")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "searching")
        self.assertEqual(data["progress"], 30)
        self.assertIn("正在搜索素材", data["currentStep"])
        mock_run.assert_awaited_once_with(created["id"])

    def test_confirm_session_api_rejects_non_confirmable_status(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        with patch("backend.api.agent.agent_service.run_confirmed_session", new_callable=AsyncMock):
            first = client.post(f"/api/agent/sessions/{created['id']}/confirm")
        second = client.post(f"/api/agent/sessions/{created['id']}/confirm")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)


if __name__ == "__main__":
    unittest.main()
