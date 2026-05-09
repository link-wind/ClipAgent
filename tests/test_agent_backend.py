import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.api.agent as agent_api_module
from backend.db.base import Base
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_session_service import AgentSessionService


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

    def test_create_session_with_prompt_generates_grounding_ready_session(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个 30 秒科技产品短视频")

        self.assertEqual(session.status, AgentStatus.PLAN_READY)
        self.assertEqual(session.messages[0].role, "user")
        self.assertEqual(session.messages[1].role, "assistant")
        self.assertIsNone(session.plan)
        self.assertIsNotNone(session.grounding)
        self.assertEqual(session.grounding.status, "needs_confirmation")
        self.assertGreater(len(session.grounding.candidates), 0)

    def test_add_user_message_to_empty_session_generates_grounding_confirmation(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()

        updated = service.add_user_message(session.id, "剪一个科技发布会预热视频")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNone(updated.plan)
        self.assertIsNotNone(updated.grounding)
        self.assertEqual(updated.grounding.status, "needs_confirmation")
        self.assertEqual(updated.messages[0].role, "user")
        self.assertEqual(updated.messages[1].role, "assistant")

    def test_add_user_message_before_grounding_confirmation_refreshes_candidates_without_creating_plan(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个 30 秒科技产品短视频")
        original_message_count = len(session.messages)

        updated = service.add_user_message(session.id, "改成更有未来感")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNone(updated.plan)
        self.assertIsNotNone(updated.grounding)
        self.assertEqual(updated.grounding.status, "needs_confirmation")
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
        self.read_service = AgentReadService(session_factory=self.session_factory)
        self.execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )
        self.patches = [
            patch.object(agent_api_module, "session_service", self.session_service),
            patch.object(agent_api_module, "read_service", self.read_service),
            patch.object(agent_api_module, "execution_service", self.execution_service),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_create_session_api_returns_plan_ready_session(self):
        from backend.main import app

        client = _make_test_client(app)
        response = client.post("/api/agent/sessions", json={"message": "做一个科技短片"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertIsNone(data["plan"])
        self.assertIn("grounding", data)
        self.assertEqual(data["grounding"]["status"], "needs_confirmation")
        self.assertGreater(len(data["grounding"]["candidates"]), 0)

    def test_create_session_api_returns_grounding_candidates_before_plan_confirmation(self):
        from backend.main import app

        client = _make_test_client(app)
        response = client.post(
            "/api/agent/sessions",
            json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertIsNone(data["plan"])
        self.assertIn("grounding", data)
        self.assertEqual(data["grounding"]["status"], "needs_confirmation")
        self.assertGreater(len(data["grounding"]["candidates"]), 0)

    def test_confirm_candidates_api_builds_grounded_plan(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post(
            "/api/agent/sessions",
            json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
        ).json()
        self.assertIn("grounding", created)
        candidate_ids = [candidate["id"] for candidate in created["grounding"]["candidates"][:2]]

        response = client.post(
            f"/api/agent/sessions/{created['id']}/grounding/confirm",
            json={"candidateIds": candidate_ids},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertEqual(data["grounding"]["status"], "confirmed")
        self.assertEqual(data["grounding"]["selectedCandidateIds"], candidate_ids)
        self.assertIsNotNone(data["plan"])
        self.assertGreater(len(data["plan"]["scenes"]), 0)

    def test_add_message_updates_existing_session(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        client.post(
            f"/api/agent/sessions/{created['id']}/grounding/confirm",
            json={"candidateIds": [candidate["id"] for candidate in created["grounding"]["candidates"][:2]]},
        )
        response = client.post(
            f"/api/agent/sessions/{created['id']}/messages",
            json={"message": "更商务一点"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertGreaterEqual(len(data["messages"]), 3)

    def test_add_message_updates_existing_plan_keywords_and_search_queries(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        client.post(
            f"/api/agent/sessions/{created['id']}/grounding/confirm",
            json={"candidateIds": [candidate["id"] for candidate in created["grounding"]["candidates"][:2]]},
        )
        response = client.post(
            f"/api/agent/sessions/{created['id']}/messages",
            json={
                "message": (
                    "把方案改成更适合真实素材检索的中文关键词："
                    "场景1：城市 车流 黄昏；"
                    "场景2：咖啡 特写 手工艺；"
                    "场景3：海边 日落 风景；"
                    "场景4：雪山 航拍 自然"
                )
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "plan_ready")
        self.assertEqual(data["plan"]["scenes"][0]["keywords"], ["城市", "车流", "黄昏"])
        self.assertEqual(data["plan"]["scenes"][0]["searchQuery"], "城市 车流 黄昏")
        self.assertEqual(data["plan"]["scenes"][1]["keywords"], ["咖啡", "特写", "手工艺"])
        self.assertEqual(data["plan"]["scenes"][1]["searchQuery"], "咖啡 特写 手工艺")

    def test_add_message_persists_new_plan_version_after_scene_keyword_edits(self):
        from backend.db.repositories import AgentPlanRepository

        created = self.session_service.create_session("做一个科技短片")
        self.session_service.confirm_grounding_candidates(
            created.id,
            [candidate.id for candidate in created.grounding.candidates[:2]],
        )

        updated = self.session_service.add_user_message(
            created.id,
            "场景1：城市 车流 黄昏；场景2：咖啡 特写 手工艺；场景3：海边 日落 风景；场景4：雪山 航拍 自然",
        )

        self.assertEqual(updated.plan.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(updated.plan.scenes[3].searchQuery, "雪山 航拍 自然")

        with self.session_factory() as db:
            latest_plan = AgentPlanRepository(db).get_latest_for_session(created.id)

        self.assertIsNotNone(latest_plan)
        self.assertEqual(latest_plan.version, 2)
        self.assertEqual(latest_plan.plan_json["scenes"][0]["keywords"], ["城市", "车流", "黄昏"])
        self.assertEqual(latest_plan.plan_json["scenes"][2]["searchQuery"], "海边 日落 风景")

    def test_add_message_before_grounding_confirmation_preserves_grounding_context(self):
        from backend.db.repositories import AgentPlanRepository

        created = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")

        updated = self.session_service.add_user_message(created.id, "整体再商务一点，目标受众改成销售团队")

        self.assertEqual(updated.status.value, "plan_ready")
        self.assertIsNone(updated.plan)
        self.assertIsNotNone(updated.grounding)
        self.assertEqual(updated.grounding.status, "needs_confirmation")
        self.assertEqual(updated.grounding.productName, "Notion")
        self.assertEqual(updated.grounding.audience, "销售团队")
        self.assertIn("Notion", updated.grounding.searchQueries)
        self.assertIn("销售团队", updated.grounding.searchQueries)
        self.assertGreaterEqual(len(updated.messages), 4)

        with self.session_factory() as db:
            latest_plan = AgentPlanRepository(db).get_latest_for_session(created.id)

        self.assertIsNone(latest_plan)

    def test_add_message_after_grounding_confirmation_preserves_grounded_plan_for_free_text_edits(self):
        from backend.db.repositories import AgentPlanRepository

        created = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        grounded = self.session_service.confirm_grounding_candidates(
            created.id,
            [candidate.id for candidate in created.grounding.candidates[:2]],
        )
        original_scene_keywords = [scene.keywords[:] for scene in grounded.plan.scenes]

        updated = self.session_service.add_user_message(created.id, "更商务一点，品牌感再强一点")

        self.assertIsNotNone(updated.plan)
        self.assertEqual(updated.grounding.status, "confirmed")
        self.assertEqual(
            [scene.keywords for scene in updated.plan.scenes],
            original_scene_keywords,
        )

        with self.session_factory() as db:
            latest_plan = AgentPlanRepository(db).get_latest_for_session(created.id)

        self.assertIsNotNone(latest_plan)
        self.assertEqual(latest_plan.version, 2)
        self.assertEqual(
            [scene["keywords"] for scene in latest_plan.plan_json["scenes"]],
            original_scene_keywords,
        )

    def test_add_message_updates_failed_planning_session_plan_when_scene_keywords_are_provided(self):
        created = self.session_service.create_session("做一个科技短片")
        grounded_session = self.session_service.confirm_grounding_candidates(
            created.id,
            [candidate.id for candidate in created.grounding.candidates[:2]],
        )

        with self.session_factory() as db:
            from backend.db.repositories import AgentSessionRepository

            session_record = AgentSessionRepository(db).get(created.id)
            session_record.status = "failed"
            session_record.error_retryable_step = "planning"
            db.commit()

        updated = self.session_service.add_user_message(
            created.id,
            "重新规划并改成中文关键词：场景1：城市 车流 黄昏；场景2：咖啡 特写 手工艺",
        )

        self.assertEqual(updated.plan.title, grounded_session.plan.title)
        self.assertEqual(updated.plan.scenes[0].keywords, ["城市", "车流", "黄昏"])
        self.assertEqual(updated.plan.scenes[1].searchQuery, "咖啡 特写 手工艺")

    def test_confirm_candidates_rejects_repeat_confirmation_without_writing_new_plan(self):
        from backend.db.repositories import AgentPlanRepository

        created = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        candidate_ids = [candidate.id for candidate in created.grounding.candidates[:2]]
        grounded = self.session_service.confirm_grounding_candidates(created.id, candidate_ids)

        with self.assertRaisesRegex(RuntimeError, "awaiting confirmation"):
            self.session_service.confirm_grounding_candidates(created.id, candidate_ids)

        with self.session_factory() as db:
            latest_plan = AgentPlanRepository(db).get_latest_for_session(created.id)

        self.assertIsNotNone(latest_plan)
        self.assertEqual(latest_plan.version, 1)
        self.assertEqual(grounded.grounding.selectedCandidateIds, candidate_ids)

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

    def test_render_shortform_video_uses_agent_local_path_as_segment_input(self):
        from backend.models.agent import ClipInfo
        from backend.services.render_service import render_shortform_video

        clip = ClipInfo(
            sceneId=1,
            sourceUrl="https://example.com/source.mp4",
            localPath="backend/downloads/agent.mp4",
            publicUrl="/downloads/agent.mp4",
            duration=6,
        )

        with patch("backend.services.render_service._render_segment") as mock_render_segment:
            with patch("backend.services.render_service._concat_segments"):
                with patch("backend.services.render_service._mix_background_music"):
                    result = render_shortform_video([clip], "out.mp4")

        segment = mock_render_segment.call_args.args[0]
        self.assertEqual(segment["input"], "backend/downloads/agent.mp4")
        self.assertEqual(result, "/output/out.mp4")

    def test_confirm_session_with_plan_starts_searching(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个科技短片")
        service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in session.grounding.candidates[:2]],
        )

        updated = service.confirm_session(session.id)

        self.assertEqual(updated.status, AgentStatus.SEARCHING)
        self.assertEqual(updated.progress, 30)
        self.assertIn("正在搜索素材", updated.currentStep)

    def test_confirm_session_rejects_searching_without_resetting_status(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个科技短片")
        service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in session.grounding.candidates[:2]],
        )
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
        service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in session.grounding.candidates[:2]],
        )
        session.status = AgentStatus.RENDERING
        session.progress = 70
        session.currentStep = "正在合成视频"

        with self.assertRaisesRegex(RuntimeError, "Session cannot be confirmed while rendering"):
            service.confirm_session(session.id)

        self.assertEqual(session.status, AgentStatus.RENDERING)
        self.assertEqual(session.progress, 70)
        self.assertEqual(session.currentStep, "正在合成视频")

    def test_confirm_session_without_plan_still_fails_with_planning_error(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()

        updated = service.confirm_session(session.id)

        self.assertEqual(updated.status, AgentStatus.FAILED)
        self.assertIsNotNone(updated.error)
        self.assertEqual(updated.error.retryableStep, "planning")

    def test_failed_planning_session_after_empty_confirm_accepts_message_and_recovers_grounding(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session()
        service.confirm_session(session.id)

        updated = service.add_user_message(session.id, "重新生成科技短片方案")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNone(updated.plan)
        self.assertIsNotNone(updated.grounding)
        self.assertEqual(updated.grounding.status, "needs_confirmation")
        self.assertIsNone(updated.error)

    def test_failed_planning_session_with_existing_plan_regenerates_plan(self):
        from backend.models.agent import AgentError, AgentStatus
        from backend.services.agent_service import AgentService

        service = AgentService()
        session = service.create_session("做一个科技短片")
        service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in session.grounding.candidates[:2]],
        )
        original_message_count = len(session.messages)
        original_title = session.plan.title
        session.status = AgentStatus.FAILED
        session.error = AgentError(message="规划失败", retryableStep="planning")

        updated = service.add_user_message(session.id, "重新规划但保留标题")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNone(updated.error)
        self.assertIsNotNone(updated.plan)
        self.assertEqual(updated.plan.title, original_title)
        self.assertEqual(len(updated.messages), original_message_count + 2)
        self.assertEqual(updated.messages[-2].role, "user")
        self.assertEqual(updated.messages[-1].role, "assistant")

    def test_agent_search_download_returns_agent_clip_paths(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate

        scene = PlanScene(
            id=7,
            description="展示产品细节",
            keywords=["product", "detail"],
            duration=5,
            searchQuery="product detail",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_search:
            with patch("backend.services.search_service.download_video", new_callable=AsyncMock) as mock_download:
                mock_search.return_value = [
                    AssetCandidate(
                        provider="youtube",
                        id="abc123",
                        title="Product detail",
                        source_url="https://www.youtube.com/watch?v=abc123",
                        download_url="https://www.youtube.com/watch?v=abc123",
                        duration=12,
                    )
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
        from backend.services.asset_providers.types import AssetCandidate

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_search:
            with patch("backend.services.search_service.download_video", new_callable=AsyncMock) as mock_download:
                mock_search.return_value = [
                    AssetCandidate(
                        provider="youtube",
                        id="bad",
                        title="Bad",
                        source_url="https://www.youtube.com/watch?v=bad",
                        download_url="https://www.youtube.com/watch?v=bad",
                        duration=12,
                    ),
                    AssetCandidate(
                        provider="youtube",
                        id="good",
                        title="Good",
                        source_url="https://www.youtube.com/watch?v=good",
                        download_url="https://www.youtube.com/watch?v=good",
                        duration=14,
                    ),
                ]
                mock_download.side_effect = [
                    Exception("YouTube said: ERROR - Precondition check failed."),
                    "backend/downloads/session_3.mp4",
                ]

                clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(mock_download.call_count, 2)
        self.assertEqual(clips[0].sourceUrl, "https://www.youtube.com/watch?v=good")

    def test_agent_download_failure_surfaces_last_external_error(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_search:
            with patch("backend.services.search_service.download_video", new_callable=AsyncMock) as mock_download:
                mock_search.return_value = [
                    AssetCandidate(
                        provider="youtube",
                        id="bad",
                        title="Bad",
                        source_url="https://www.youtube.com/watch?v=bad",
                        download_url="https://www.youtube.com/watch?v=bad",
                        duration=12,
                    ),
                    AssetCandidate(
                        provider="youtube",
                        id="worse",
                        title="Worse",
                        source_url="https://www.youtube.com/watch?v=worse",
                        download_url="https://www.youtube.com/watch?v=worse",
                        duration=14,
                    ),
                ]
                mock_download.side_effect = [
                    Exception("Download failed: YouTube said: Sign in to confirm you’re not a bot."),
                    Exception("Download failed: YouTube 当前要求 PO Token"),
                ]

                with self.assertRaisesRegex(RuntimeError, "YouTube 当前要求 PO Token"):
                    asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(mock_download.call_count, 2)

    def test_agent_search_failure_surfaces_external_error(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_search:
            mock_search.side_effect = RuntimeError("YouTube said: Sign in to confirm you’re not a bot.")

            with self.assertRaisesRegex(RuntimeError, "Sign in to confirm"):
                asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

    def test_agent_download_falls_back_from_youtube_search_failure_to_pexels(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
            author="Pexels Creator",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_youtube_search, patch(
            "backend.services.search_service.search_pexels_candidates",
        ) as mock_pexels_search, patch(
            "backend.services.search_service.download_pexels_candidate",
        ) as mock_pexels_download, patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_youtube_search.side_effect = RuntimeError("素材搜索失败：Sign in to confirm you’re not a bot.")
            mock_pexels_search.return_value = [pexels_candidate]
            mock_pexels_download.return_value = AssetDownload(
                local_path="backend/downloads/session_3.mp4",
                public_url="/downloads/session_3.mp4",
                metadata=pexels_candidate.to_metadata(),
            )
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(clips[0].localPath, "backend/downloads/session_3.mp4")

    def test_agent_download_falls_back_from_youtube_download_failure_to_pexels(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        youtube_candidate = AssetCandidate(
            provider="youtube",
            id="bad",
            title="Bad",
            source_url="https://www.youtube.com/watch?v=bad",
            download_url="https://www.youtube.com/watch?v=bad",
            duration=12,
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
        )

        with patch("backend.services.search_service.search_youtube_candidates", return_value=[youtube_candidate]), patch(
            "backend.services.search_service.download_video",
            new_callable=AsyncMock,
        ) as mock_download, patch(
            "backend.services.search_service.search_pexels_candidates",
            return_value=[pexels_candidate],
        ), patch(
            "backend.services.search_service.download_pexels_candidate",
            return_value=AssetDownload(
                local_path="backend/downloads/session_3_pexels_1.mp4",
                public_url="/downloads/session_3_pexels_1.mp4",
                metadata=pexels_candidate.to_metadata(),
            ),
        ), patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_download.side_effect = Exception("Download failed: YouTube 当前要求 PO Token")
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(clips[0].publicUrl, "/downloads/session_3_pexels_1.mp4")

    def test_agent_download_prefers_default_youtube_provider_order(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        youtube_candidate = AssetCandidate(
            provider="youtube",
            id="good-youtube",
            title="Good Youtube",
            source_url="https://www.youtube.com/watch?v=good-youtube",
            download_url="https://www.youtube.com/watch?v=good-youtube",
            duration=12,
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
        )

        with patch("backend.services.search_service.search_youtube_candidates", return_value=[youtube_candidate]), patch(
            "backend.services.search_service.search_pexels_candidates",
            return_value=[pexels_candidate],
        ), patch(
            "backend.services.search_service.download_video",
            new_callable=AsyncMock,
            return_value="backend/downloads/session_3.mp4",
        ) as mock_download, patch(
            "backend.services.search_service.download_pexels_candidate",
        ) as mock_pexels_download, patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.youtube.com/watch?v=good-youtube")
        self.assertEqual(mock_download.call_count, 1)
        self.assertEqual(mock_pexels_download.call_count, 0)

    def test_agent_download_respects_configured_provider_order(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        youtube_candidate = AssetCandidate(
            provider="youtube",
            id="good-youtube",
            title="Good Youtube",
            source_url="https://www.youtube.com/watch?v=good-youtube",
            download_url="https://www.youtube.com/watch?v=good-youtube",
            duration=12,
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
        )

        with patch.dict("os.environ", {"CLIPFORGE_ASSET_PROVIDER_ORDER": "pexels,youtube"}, clear=False), patch(
            "backend.services.search_service.search_youtube_candidates",
            return_value=[youtube_candidate],
        ), patch(
            "backend.services.search_service.search_pexels_candidates",
            return_value=[pexels_candidate],
        ), patch(
            "backend.services.search_service.download_video",
            new_callable=AsyncMock,
            return_value="backend/downloads/session_3.mp4",
        ) as mock_download, patch(
            "backend.services.search_service.download_pexels_candidate",
            return_value=AssetDownload(
                local_path="backend/downloads/session_3_pexels_1.mp4",
                public_url="/downloads/session_3_pexels_1.mp4",
                metadata=pexels_candidate.to_metadata(),
            ),
        ) as mock_pexels_download, patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(mock_pexels_download.call_count, 1)
        self.assertEqual(mock_download.call_count, 0)

    def test_agent_download_stops_searching_after_first_provider_returns_candidates(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
        )

        with patch.dict("os.environ", {"CLIPFORGE_ASSET_PROVIDER_ORDER": "pexels,youtube"}, clear=False), patch(
            "backend.services.search_service.search_pexels_candidates",
            return_value=[pexels_candidate],
        ) as mock_pexels_search, patch(
            "backend.services.search_service.search_youtube_candidates",
            side_effect=AssertionError("should not search fallback provider after first provider returns candidates"),
        ) as mock_youtube_search, patch(
            "backend.services.search_service.download_pexels_candidate",
            return_value=AssetDownload(
                local_path="backend/downloads/session_3_pexels_1.mp4",
                public_url="/downloads/session_3_pexels_1.mp4",
                metadata=pexels_candidate.to_metadata(),
            ),
        ) as mock_pexels_download, patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(mock_pexels_search.call_count, 1)
        self.assertEqual(mock_pexels_download.call_count, 1)
        self.assertEqual(mock_youtube_search.call_count, 0)

    def test_all_provider_failure_surfaces_safe_summaries(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )

        with patch("backend.services.search_service.search_youtube_candidates") as mock_youtube_search, patch(
            "backend.services.search_service.search_pexels_candidates",
        ) as mock_pexels_search, patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_youtube_search.side_effect = RuntimeError("素材搜索失败：Sign in to confirm you’re not a bot.")
            mock_pexels_search.side_effect = RuntimeError("Pexels 搜索失败：HTTP 401 Unauthorized")
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            with self.assertRaisesRegex(RuntimeError, "youtube.*Sign in.*pexels.*401"):
                asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

    def test_provider_failure_message_dedupes_and_keeps_specific_diagnostics(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scenes = [
            PlanScene(
                id=1,
                description="产品使用场景",
                keywords=["product", "workflow"],
                duration=6,
                searchQuery="product workflow",
            ),
            PlanScene(
                id=2,
                description="产品细节特写",
                keywords=["product", "detail"],
                duration=6,
                searchQuery="product detail",
            ),
        ]

        with patch("backend.services.search_service.get_asset_provider_order", return_value=["pexels"]), patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = ""

            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(search_service.search_and_download_agent_clips("session", scenes))

        message = str(ctx.exception)
        self.assertEqual(message.count("缺少 PEXELS_API_KEY，已跳过 Pexels 素材源"), 1)
        self.assertNotIn("pexels: 没有返回候选素材", message)

    def test_all_scene_failures_expose_structured_diagnostics(self):
        from backend.services.search_service import AgentSceneSearchFailure

        exc = AgentSceneSearchFailure(
            "没有下载到可用素材",
            failed_scene_ids=[1, 2],
            failure_category="no_inventory",
            primary_provider="youtube",
            provider_diagnostics=[
                {"provider": "youtube", "message": "没有返回候选素材"},
            ],
            scene_diagnostics=[
                {
                    "sceneId": 1,
                    "retryable": True,
                    "summary": "youtube returned no candidates",
                }
            ],
            retry_strategy_hint="inventory_broaden",
        )

        self.assertEqual(exc.failed_scene_ids, [1, 2])
        self.assertEqual(exc.failure_category, "no_inventory")
        self.assertEqual(exc.primary_provider, "youtube")
        self.assertEqual(
            exc.provider_diagnostics,
            [{"provider": "youtube", "message": "没有返回候选素材"}],
        )
        self.assertEqual(
            exc.scene_diagnostics,
            [
                {
                    "sceneId": 1,
                    "retryable": True,
                    "summary": "youtube returned no candidates",
                }
            ],
        )
        self.assertEqual(exc.retry_strategy_hint, "inventory_broaden")

    def test_repeated_scene_provider_failures_are_collapsed_into_summary(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service

        scenes = [
            PlanScene(
                id=1,
                description="产品使用场景",
                keywords=["product", "workflow"],
                duration=6,
                searchQuery="product workflow",
            ),
            PlanScene(
                id=2,
                description="产品细节特写",
                keywords=["product", "detail"],
                duration=6,
                searchQuery="product detail",
            ),
            PlanScene(
                id=3,
                description="品牌氛围镜头",
                keywords=["brand", "mood"],
                duration=6,
                searchQuery="brand mood",
            ),
        ]

        with patch("backend.services.search_service.get_asset_provider_order", return_value=["pexels"]), patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config, patch(
            "backend.services.search_service.search_pexels_candidates",
        ) as mock_pexels_search:
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"
            mock_pexels_search.side_effect = [
                RuntimeError("Pexels 搜索失败：HTTP 401 Unauthorized for query product workflow"),
                RuntimeError("Pexels 搜索失败：HTTP 401 Unauthorized for query product detail"),
                RuntimeError("Pexels 搜索失败：HTTP 401 Unauthorized for query brand mood"),
            ]

            with self.assertRaises(RuntimeError) as ctx:
                asyncio.run(search_service.search_and_download_agent_clips("session", scenes))

        message = str(ctx.exception)
        self.assertEqual(message.count("Pexels 搜索失败"), 1)
        self.assertIn("HTTP 401 Unauthorized", message)
        self.assertIn("3 次", message)
        self.assertNotIn("product detail", message)
        self.assertNotIn("brand mood", message)
        self.assertNotIn("pexels: 没有返回候选素材", message)

    def test_asset_candidate_exposes_legacy_video_info(self):
        from backend.services.asset_providers.types import AssetCandidate

        candidate = AssetCandidate(
            provider="youtube",
            id="abc123",
            title="Demo",
            source_url="https://www.youtube.com/watch?v=abc123",
            download_url="https://www.youtube.com/watch?v=abc123",
            duration=12.5,
            thumbnail="https://example.com/thumb.jpg",
            author="Clip Channel",
            diagnostics={"client": "web"},
        )

        self.assertEqual(
            candidate.to_legacy_video_info(),
            {
                "id": "abc123",
                "title": "Demo",
                "url": "https://www.youtube.com/watch?v=abc123",
                "duration": 12.5,
                "thumbnail": "https://example.com/thumb.jpg",
                "provider": "youtube",
                "downloadUrl": "https://www.youtube.com/watch?v=abc123",
                "author": "Clip Channel",
                "diagnostics": {"client": "web"},
            },
        )

    def test_clip_metadata_sidecar_round_trips_by_local_path(self):
        from backend.services.asset_providers.metadata import pop_clip_metadata, remember_clip_metadata

        remember_clip_metadata(
            "backend/downloads/session_1.mp4",
            {
                "provider": "pexels",
                "providerId": "42",
                "author": "Pexels Creator",
            },
        )

        self.assertEqual(
            pop_clip_metadata("backend/downloads/session_1.mp4"),
            {
                "provider": "pexels",
                "providerId": "42",
                "author": "Pexels Creator",
            },
        )
        self.assertEqual(pop_clip_metadata("backend/downloads/session_1.mp4"), {})

    def test_youtube_search_surfaces_external_error(self):
        from backend.services.search_service import search_youtube

        with patch("yt_dlp.YoutubeDL") as mock_youtube_dl:
            ydl = mock_youtube_dl.return_value.__enter__.return_value
            ydl.extract_info.side_effect = Exception("Sign in to confirm you’re not a bot.")

            with self.assertRaisesRegex(RuntimeError, "Sign in to confirm"):
                search_youtube(["product", "workflow"], max_results=3)

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

        self.assertEqual(search_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web_safari", "web"])
        self.assertEqual(download_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web_safari", "web"])
        self.assertEqual(download_options["js_runtimes"], {"node": {}})
        self.assertIn("ejs:npm", download_options["remote_components"])

    def test_youtube_options_use_hardening_environment(self):
        from backend.services.search_service import build_download_options, build_search_options

        with patch.dict(
            "os.environ",
            {
                "YTDLP_COOKIES_FILE": "/tmp/youtube.cookies.txt",
                "YTDLP_PLAYER_CLIENTS": "mweb,web",
                "YTDLP_PO_TOKEN": "web.gvs+token-value",
                "YTDLP_IMPERSONATE": "chrome",
                "YTDLP_FORMAT": "best[height<=480][ext=mp4]",
            },
            clear=False,
        ):
            search_options = build_search_options()
            download_options = build_download_options("backend/downloads/example.mp4", [])

        self.assertEqual(search_options["cookiefile"], "/tmp/youtube.cookies.txt")
        self.assertEqual(download_options["cookiefile"], "/tmp/youtube.cookies.txt")
        self.assertEqual(search_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web"])
        self.assertEqual(download_options["extractor_args"]["youtube"]["player_client"], ["mweb", "web"])
        self.assertEqual(search_options["extractor_args"]["youtube"]["po_token"], ["web.gvs+token-value"])
        self.assertEqual(download_options["extractor_args"]["youtube"]["po_token"], ["web.gvs+token-value"])
        self.assertEqual(search_options["impersonate"], "chrome")
        self.assertEqual(download_options["impersonate"], "chrome")
        self.assertEqual(download_options["format"], "best[height<=480][ext=mp4]")

    def test_provider_boolean_env_parsing(self):
        from backend.services.asset_providers.config import env_flag

        with patch.dict("os.environ", {"YTDLP_PROVIDER_ENABLED": "false", "PEXELS_PROVIDER_ENABLED": "1"}, clear=False):
            self.assertFalse(env_flag("YTDLP_PROVIDER_ENABLED", default=True))
            self.assertTrue(env_flag("PEXELS_PROVIDER_ENABLED", default=False))

    def test_fixture_provider_config_uses_defaults(self):
        from backend.services.asset_providers.config import get_fixture_config

        with patch.dict("os.environ", {}, clear=True):
            config = get_fixture_config()

        self.assertTrue(config.enabled)
        self.assertEqual(config.library_path, "fixtures/videos.json")

    def test_fixture_library_loads_default_videos_json(self):
        from backend.services.asset_providers.fixture import load_fixture_library

        with patch.dict("os.environ", {}, clear=True):
            library = load_fixture_library()

        self.assertIsInstance(library, list)
        self.assertGreater(len(library), 0)
        self.assertIsInstance(library[0], dict)
        self.assertIn("id", library[0])
        self.assertIn("videoUrl", library[0])
        self.assertIn("thumbnailUrl", library[0])

    def test_fixture_search_returns_normalized_candidates(self):
        from backend.services.asset_providers.fixture import search_fixture_candidates

        with patch.dict("os.environ", {}, clear=True):
            candidates = search_fixture_candidates(["  城市 ", "夜景"], max_results=3)

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.provider, "fixture")
        self.assertEqual(candidate.id, "vid_001")
        self.assertEqual(candidate.title, "城市黄昏车流")
        self.assertEqual(candidate.source_url, "/fixtures/vid_001.mp4")
        self.assertEqual(candidate.download_url, "/fixtures/vid_001.mp4")
        self.assertEqual(candidate.thumbnail, "/fixtures/thumbnails/vid_001.jpg")
        self.assertEqual(candidate.duration, 45)
        self.assertEqual(
            candidate.diagnostics,
            {
                "score": 2,
                "matchedKeywords": ["城市", "夜景"],
            },
        )

    def test_fixture_search_returns_empty_list_when_no_match(self):
        from backend.services.asset_providers.fixture import search_fixture_candidates

        with patch.dict("os.environ", {}, clear=True):
            candidates = search_fixture_candidates(["沙漠", "极光"], max_results=5)

        self.assertEqual(candidates, [])

    def test_fixture_search_prefers_probed_media_duration_when_local_file_exists(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from backend.services.asset_providers import fixture as fixture_provider
        from backend.services.asset_providers.fixture import search_fixture_candidates

        with TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            fixtures_dir = temp_root / "fixtures"
            fixtures_dir.mkdir(parents=True)
            (fixtures_dir / "videos.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "vid_001",
                            "title": "城市黄昏车流",
                            "description": "傍晚城市街道，车流穿梭，霓虹初上",
                            "duration": 45,
                            "tags": ["城市", "黄昏", "车流", "夜景"],
                            "thumbnailUrl": "/fixtures/thumbnails/vid_001.jpg",
                            "videoUrl": "/fixtures/vid_001.mp4",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (fixtures_dir / "vid_001.mp4").write_bytes(b"fixture-mp4-bytes")

            with patch.object(fixture_provider, "ROOT_DIR", temp_root), patch(
                "backend.services.asset_providers.fixture.probe_fixture_duration",
                return_value=1.0,
            ), patch.dict("os.environ", {}, clear=True):
                candidates = search_fixture_candidates(["城市", "车流"], max_results=1)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].duration, 1.0)

    def test_fixture_download_copies_asset_into_backend_downloads(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from backend.services.asset_providers import fixture as fixture_provider
        from backend.services.asset_providers.fixture import download_fixture_candidate, search_fixture_candidates

        with TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            fixtures_dir = temp_root / "fixtures"
            downloads_dir = temp_root / "backend" / "downloads"
            fixtures_dir.mkdir(parents=True)
            downloads_dir.mkdir(parents=True)
            (fixtures_dir / "videos.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "vid_001",
                            "title": "城市黄昏车流",
                            "description": "傍晚城市街道，车流穿梭，霓虹初上",
                            "duration": 45,
                            "tags": ["城市", "黄昏", "车流", "夜景"],
                            "thumbnailUrl": "/fixtures/thumbnails/vid_001.jpg",
                            "videoUrl": "/fixtures/vid_001.mp4",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            source_path = fixtures_dir / "vid_001.mp4"
            source_bytes = b"fixture-mp4-bytes"
            source_path.write_bytes(source_bytes)

            with patch.object(fixture_provider, "ROOT_DIR", temp_root), patch.object(
                fixture_provider,
                "DOWNLOADS_DIR",
                str(downloads_dir),
            ), patch.dict("os.environ", {}, clear=True):
                candidate = search_fixture_candidates(["城市", "车流"], max_results=1)[0]
                download = download_fixture_candidate("session", candidate, 1, "session_1_fixture_1.mp4")

            self.assertTrue(download.local_path.endswith("backend/downloads/session_1_fixture_1.mp4"))
            self.assertEqual(download.public_url, "/downloads/session_1_fixture_1.mp4")
            self.assertIn("provider", download.metadata)
            self.assertEqual(Path(download.local_path).read_bytes(), source_bytes)

    def test_fixture_download_raises_clear_error_when_source_file_missing(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from backend.services.asset_providers import fixture as fixture_provider
        from backend.services.asset_providers.fixture import download_fixture_candidate
        from backend.services.asset_providers.types import AssetCandidate

        candidate = AssetCandidate(
            provider="fixture",
            id="missing",
            title="missing",
            source_url="/fixtures/missing.mp4",
            download_url="/fixtures/missing.mp4",
            duration=10,
        )

        with TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            downloads_dir = temp_root / "backend" / "downloads"
            downloads_dir.mkdir(parents=True)

            with patch.object(fixture_provider, "ROOT_DIR", temp_root), patch.object(
                fixture_provider,
                "DOWNLOADS_DIR",
                str(downloads_dir),
            ):
                with self.assertRaisesRegex(RuntimeError, "本地素材文件不存在"):
                    download_fixture_candidate("session", candidate, 1, "missing.mp4")

    def test_agent_download_can_complete_with_fixture_provider(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers import fixture as fixture_provider

        scene = PlanScene(
            id=1,
            description="城市演示镜头",
            keywords=["城市", "车流"],
            duration=6,
            searchQuery="城市 车流",
        )

        with TemporaryDirectory() as tmpdir:
            temp_root = Path(tmpdir)
            fixtures_dir = temp_root / "fixtures"
            downloads_dir = temp_root / "backend" / "downloads"
            fixtures_dir.mkdir(parents=True)
            downloads_dir.mkdir(parents=True)
            (fixtures_dir / "videos.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "vid_001",
                            "title": "城市黄昏车流",
                            "description": "傍晚城市街道，车流穿梭，霓虹初上",
                            "duration": 45,
                            "tags": ["城市", "黄昏", "车流", "夜景"],
                            "thumbnailUrl": "/fixtures/thumbnails/vid_001.jpg",
                            "videoUrl": "/fixtures/vid_001.mp4",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (fixtures_dir / "vid_001.mp4").write_bytes(b"fixture-mp4-bytes")

            with patch.object(fixture_provider, "ROOT_DIR", temp_root), patch.object(
                fixture_provider,
                "DOWNLOADS_DIR",
                str(downloads_dir),
            ), patch.dict(
                "os.environ",
                {"CLIPFORGE_ASSET_PROVIDER_ORDER": "fixture", "FIXTURE_PROVIDER_ENABLED": "true"},
                clear=False,
            ):
                clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sceneId, 1)
        self.assertEqual(clips[0].caption, "城市演示镜头")
        self.assertEqual(clips[0].sourceUrl, "/fixtures/vid_001.mp4")
        self.assertTrue(clips[0].localPath.endswith(".mp4"))

    def test_fixture_provider_falls_through_to_next_provider_when_no_match(self):
        from backend.models.agent import PlanScene
        from backend.services import search_service
        from backend.services.asset_providers.types import AssetCandidate, AssetDownload

        scene = PlanScene(
            id=3,
            description="产品使用场景",
            keywords=["product", "workflow"],
            duration=6,
            searchQuery="product workflow",
        )
        pexels_candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/101.mp4",
            duration=14,
        )

        with patch.dict("os.environ", {"CLIPFORGE_ASSET_PROVIDER_ORDER": "fixture,pexels"}, clear=False), patch(
            "backend.services.search_service.search_pexels_candidates",
            return_value=[pexels_candidate],
        ), patch(
            "backend.services.search_service.download_pexels_candidate",
            return_value=AssetDownload(
                local_path="backend/downloads/session_3_pexels_1.mp4",
                public_url="/downloads/session_3_pexels_1.mp4",
                metadata=pexels_candidate.to_metadata(),
            ),
        ) as mock_download, patch(
            "backend.services.search_service.get_pexels_config",
        ) as mock_pexels_config:
            mock_pexels_config.return_value.enabled = True
            mock_pexels_config.return_value.api_key = "pexels-key"

            clips = asyncio.run(search_service.search_and_download_agent_clips("session", [scene]))

        self.assertEqual(len(clips), 1)
        self.assertEqual(clips[0].sourceUrl, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(mock_download.call_count, 1)

    def test_pexels_search_maps_api_response_to_candidates(self):
        import json
        from unittest.mock import MagicMock

        from backend.services.asset_providers.pexels import search_pexels_candidates

        response_payload = {
            "videos": [
                {
                    "id": 101,
                    "url": "https://www.pexels.com/video/demo-101/",
                    "duration": 9,
                    "width": 1080,
                    "height": 1920,
                    "image": "https://images.pexels.com/videos/101/thumb.jpg",
                    "user": {"name": "Pexels Creator", "url": "https://www.pexels.com/@creator"},
                    "video_files": [
                        {
                            "id": 1,
                            "quality": "hd",
                            "file_type": "video/mp4",
                            "width": 720,
                            "height": 1280,
                            "link": "https://videos.pexels.com/video-files/101/portrait.mp4",
                        }
                    ],
                }
            ]
        }
        fake_response = MagicMock()
        fake_response.status = 200
        fake_response.read.return_value = json.dumps(response_payload).encode("utf-8")
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with patch.dict("os.environ", {"PEXELS_API_KEY": "pexels-key"}, clear=False), patch(
            "urllib.request.urlopen",
            return_value=fake_response,
        ) as mock_urlopen:
            candidates = search_pexels_candidates(["product", "demo"], max_results=3)

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "pexels-key")
        self.assertEqual(request.headers["Accept"], "application/json")
        self.assertEqual(request.headers["User-agent"], "ClipForge/1.0")
        self.assertIn("/v1/videos/search", request.full_url)
        self.assertIn("orientation=portrait", request.full_url)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].provider, "pexels")
        self.assertEqual(candidates[0].id, "101")
        self.assertEqual(candidates[0].source_url, "https://www.pexels.com/video/demo-101/")
        self.assertEqual(candidates[0].download_url, "https://videos.pexels.com/video-files/101/portrait.mp4")
        self.assertEqual(candidates[0].author, "Pexels Creator")

    def test_pexels_selects_vertical_mp4_with_bounded_resolution(self):
        from backend.services.asset_providers.pexels import select_pexels_video_file

        selected = select_pexels_video_file(
            [
                {"file_type": "video/mp4", "width": 3840, "height": 2160, "link": "landscape-4k.mp4"},
                {"file_type": "video/mp4", "width": 720, "height": 1280, "link": "portrait-720.mp4"},
                {"file_type": "video/webm", "width": 720, "height": 1280, "link": "portrait.webm"},
            ]
        )

        self.assertEqual(selected["link"], "portrait-720.mp4")

    def test_pexels_direct_download_writes_mp4(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import MagicMock

        from backend.services.asset_providers.pexels import download_pexels_candidate
        from backend.services.asset_providers.types import AssetCandidate

        candidate = AssetCandidate(
            provider="pexels",
            id="101",
            title="Pexels video 101",
            source_url="https://www.pexels.com/video/demo-101/",
            download_url="https://videos.pexels.com/video-files/101/portrait.mp4",
            duration=9,
            width=720,
            height=1280,
            author="Pexels Creator",
        )
        fake_response = MagicMock()
        fake_response.status = 200
        fake_response.read.return_value = b"\x00\x00\x00\x18ftypmp42video-bytes"
        fake_response.__enter__.return_value = fake_response
        fake_response.__exit__.return_value = None

        with TemporaryDirectory() as tmp_dir, patch(
            "backend.services.asset_providers.pexels.DOWNLOADS_DIR",
            tmp_dir,
        ), patch("urllib.request.urlopen", return_value=fake_response):
            download = download_pexels_candidate("session", candidate, scene_id=4, output_filename="session_4.mp4")

            output_path = Path(tmp_dir) / "session_4.mp4"
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), b"\x00\x00\x00\x18ftypmp42video-bytes")
            self.assertEqual(download.local_path, str(output_path))
            self.assertEqual(download.public_url, "/downloads/session_4.mp4")
            self.assertEqual(download.metadata["provider"], "pexels")
            self.assertEqual(download.metadata["author"], "Pexels Creator")

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
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        event.listen(self.engine, "connect", AgentApiTests._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self.session_service = AgentSessionService(session_factory=self.session_factory)
        self.read_service = AgentReadService(session_factory=self.session_factory)
        self.execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )
        self.patches = [
            patch.object(agent_api_module, "session_service", self.session_service),
            patch.object(agent_api_module, "read_service", self.read_service),
            patch.object(agent_api_module, "execution_service", self.execution_service),
        ]
        for patcher in self.patches:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()
        self.engine.dispose()

    def test_frontend_store_supports_recovery_fields(self):
        store_source = (ROOT / "src" / "stores" / "useAgentStore.ts").read_text(encoding="utf-8")
        api_source = (ROOT / "src" / "lib" / "agentApi.ts").read_text(encoding="utf-8")

        self.assertIn("activeSessionId", store_source)
        self.assertIn("events", store_source)
        self.assertIn("setActiveSessionId", store_source)
        self.assertIn("setEvents", store_source)
        self.assertIn("getAgentSessionEvents", api_source)
        self.assertIn("queued", api_source)

    def test_workspace_polls_running_sessions_and_restores_events(self):
        workspace_source = (ROOT / "src" / "components" / "agent" / "AgentWorkspace.tsx").read_text(
            encoding="utf-8"
        )
        progress_source = (ROOT / "src" / "components" / "agent" / "ProgressPanel.tsx").read_text(
            encoding="utf-8"
        )
        result_source = (ROOT / "src" / "components" / "agent" / "ResultPanel.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("getAgentSessionEvents", workspace_source)
        self.assertIn("activeSessionId", workspace_source)
        self.assertIn("queued", workspace_source)
        self.assertIn("setSession({ ...nextSession, events: nextEvents })", workspace_source)
        self.assertIn("session?.events", progress_source)
        self.assertIn("activeJobId", result_source)

    def test_workspace_page_is_tailwind_based(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("BriefWorkspacePage.module.css", workspace_source)
        self.assertNotIn("styles.", workspace_source)
        self.assertIn("className=\"min-h-full", workspace_source)
        self.assertIn("grid w-full max-w-[980px]", workspace_source)

    def test_workspace_handoff_renders_execution_steps_and_result_states(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("EXECUTION_STEP_IDS", workspace_source)
        self.assertIn("create_task", workspace_source)
        self.assertIn("search_assets", workspace_source)
        self.assertIn("prepare_assets", workspace_source)
        self.assertIn("render_video", workspace_source)
        self.assertIn("执行交接", workspace_source)
        self.assertIn("activeJobId", workspace_source)
        self.assertIn("查看任务详情", workspace_source)
        self.assertIn("结果预览", workspace_source)
        self.assertIn("失败步骤", workspace_source)

    def test_workspace_renders_candidate_confirmation_stage(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("候选产品画面确认", workspace_source)
        self.assertIn("确认这些画面", workspace_source)
        self.assertIn("grounding", workspace_source)
        self.assertIn("selectedCandidateIds", workspace_source)

    def test_workspace_restore_experience_renders_resume_actions(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("restoredSessionId", workspace_source)
        self.assertIn("setRestoredSessionId(activeSessionId)", workspace_source)
        self.assertIn("已恢复到当前方案会话", workspace_source)
        self.assertIn("当前状态：", workspace_source)
        self.assertIn("getWorkspaceStatus(session)", workspace_source)
        self.assertIn("session?.activeJobId", workspace_source)
        self.assertIn("查看任务列表", workspace_source)
        self.assertIn("href=\"/tasks\"", workspace_source)
        self.assertIn("继续补充方案", workspace_source)
        self.assertIn("focusComposer", workspace_source)
        self.assertIn("textareaRef", workspace_source)

    def test_workspace_confirm_applies_pending_message_before_confirming(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("const pendingMessage = message.trim();", workspace_source)
        self.assertIn("pendingMessage ? await sendAgentMessage(session.id, pendingMessage) : session", workspace_source)
        self.assertIn("const nextSession = await confirmAgentSession(sessionToConfirm.id);", workspace_source)
        self.assertIn("setMessage('');", workspace_source)

    def test_workspace_grounding_selection_does_not_resync_from_polling_results(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("setSelectedCandidateIds(session?.grounding?.selectedCandidateIds ?? []);", workspace_source)
        self.assertNotIn("}, [session?.id, session?.grounding?.selectedCandidateIds]);", workspace_source)
        self.assertIn("setSelectedCandidateIds((current) =>", workspace_source)

    def test_workspace_grounding_confirm_does_not_submit_pending_message_before_confirming(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("const nextSession = await confirmGroundingCandidates(session.id, selectedCandidateIds);", workspace_source)
        self.assertIn("const sessionToConfirm = pendingMessage ? await sendAgentMessage(session.id, pendingMessage) : session;", workspace_source)
        self.assertNotIn("const sessionToConfirm = pendingMessage ? await sendAgentMessage(session.id, pendingMessage) : session;\n      const nextSession = await confirmGroundingCandidates(sessionToConfirm.id, selectedCandidateIds);", workspace_source)
        self.assertIn("const canConfirmGrounding = awaitingGroundingConfirmation && selectedCandidateIds.length > 0 && !isSubmitting && !trimmedMessage;", workspace_source)

    def test_workspace_grounding_confirmation_renders_candidate_visual_previews(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("candidate.previewUrl || candidate.imageUrl", workspace_source)
        self.assertIn("alt={candidate.title}", workspace_source)
        self.assertIn("className=\"h-24 w-24", workspace_source)

    def test_workspace_restore_experience_can_jump_to_result_failure_or_execution(self):
        workspace_source = (ROOT / "src" / "components" / "workspace" / "BriefWorkspacePage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("hasAppliedRestoreJump", workspace_source)
        self.assertIn("executionSectionRef", workspace_source)
        self.assertIn("resultSectionRef", workspace_source)
        self.assertIn("failureSectionRef", workspace_source)
        self.assertIn("resultSectionRef.current", workspace_source)
        self.assertIn("failureSectionRef.current", workspace_source)
        self.assertIn("executionSectionRef.current", workspace_source)
        self.assertIn("scrollIntoView({ behavior: 'smooth', block: 'start' })", workspace_source)
        self.assertIn("setHasAppliedRestoreJump(true)", workspace_source)

    def test_tasks_concept_pages_share_mock_data_and_cover_three_layouts(self):
        concepts_index = (ROOT / "src" / "app" / "tasks" / "concepts" / "page.tsx").read_text(encoding="utf-8")
        b1_source = (ROOT / "src" / "app" / "tasks" / "concepts" / "b1" / "page.tsx").read_text(
            encoding="utf-8"
        )
        b2_source = (ROOT / "src" / "app" / "tasks" / "concepts" / "b2" / "page.tsx").read_text(
            encoding="utf-8"
        )
        b3_source = (ROOT / "src" / "app" / "tasks" / "concepts" / "b3" / "page.tsx").read_text(
            encoding="utf-8"
        )
        mock_source = (ROOT / "src" / "components" / "tasks" / "concepts" / "mockTaskConceptData.ts").read_text(
            encoding="utf-8"
        )

        self.assertIn("/tasks/concepts/b1", concepts_index)
        self.assertIn("/tasks/concepts/b2", concepts_index)
        self.assertIn("/tasks/concepts/b3", concepts_index)
        self.assertIn("taskConceptSummaries", b1_source)
        self.assertIn("taskConceptSummaries", b2_source)
        self.assertIn("taskConceptSummaries", b3_source)
        self.assertIn("列表 + 弹窗详情", b1_source)
        self.assertIn("列表 + 右侧详情面板", b2_source)
        self.assertIn("独立详情页", b3_source)
        self.assertIn("videoUrl", mock_source)
        self.assertIn("clips", mock_source)
        self.assertIn("events", mock_source)
        self.assertIn("steps", mock_source)

    def test_tasks_page_is_tailwind_based(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("TaskManagerPage.module.css", tasks_source)
        self.assertNotIn("styles.", tasks_source)
        self.assertIn("className=\"grid min-w-0 gap-4", tasks_source)
        self.assertIn("aria-label=\"任务列表\"", tasks_source)

    def test_tasks_modal_renders_b1_sections(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("列表 + 弹窗详情", tasks_source)
        self.assertIn("任务详情", tasks_source)
        self.assertIn("状态摘要", tasks_source)
        self.assertIn("标准步骤", tasks_source)
        self.assertIn("事件时间线", tasks_source)
        self.assertIn("素材与结果", tasks_source)
        self.assertIn("activeTask.videoUrl", tasks_source)
        self.assertIn("activeTask.clips", tasks_source)

    def test_tasks_modal_actions_wire_refresh_and_workspace_jump(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("const [isRefreshingTaskDetail, setIsRefreshingTaskDetail] = useState(false);", tasks_source)
        self.assertIn("setActiveSessionId(activeTask.sessionId);", tasks_source)
        self.assertIn("router.push('/workspace');", tasks_source)
        self.assertIn("刷新中", tasks_source)

    def test_tasks_workspace_jump_clears_session_before_setting_active_session(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("setSession(null);", tasks_source)
        self.assertIn("setActiveSessionId(activeTask.sessionId);", tasks_source)
        self.assertLess(tasks_source.index("setSession(null);"), tasks_source.index("setActiveSessionId(activeTask.sessionId);"))

    def test_tasks_retry_action_is_disabled_with_guidance_copy(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("任务级重新执行暂未开放，请返回方案页重新发起。", tasks_source)
        self.assertIn("disabled", tasks_source)
        self.assertIn("activeTask.status === 'failed' || activeTask.status === 'error'", tasks_source)

    def test_tasks_list_rows_do_not_render_active_retry_action(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("text-rose-700 transition hover:text-rose-800", tasks_source)
        self.assertNotIn(">\\n                          重试\\n                        </button>", tasks_source)

    def test_tasks_operations_console_copy(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("任务控制台", tasks_source)
        self.assertIn("统一扫读任务状态、最近活动和结果入口", tasks_source)
        self.assertIn("失败优先关注", tasks_source)
        self.assertIn("结果直达", tasks_source)

    def test_tasks_row_actions_include_workspace_and_result_paths(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("const [taskVideoUrls, setTaskVideoUrls] = useState<Record<string, string>>({});", tasks_source)
        self.assertIn("function openTaskResult(taskId: string)", tasks_source)
        self.assertIn("taskVideoUrls[task.id]", tasks_source)
        self.assertIn("打开结果", tasks_source)
        self.assertIn("查看方案", tasks_source)

    def test_tasks_batch_action_is_honest_placeholder(self):
        tasks_source = (ROOT / "src" / "components" / "tasks" / "TaskManagerPage.tsx").read_text(
            encoding="utf-8"
        )

        self.assertIn("批量操作将在后续阶段开放", tasks_source)
        self.assertIn("本阶段先支持单任务查看、回到方案和结果直达。", tasks_source)
        self.assertIn("disabled", tasks_source)

    def test_agent_chat_resets_stale_session_on_missing_backend_session(self):
        content = (ROOT / "src" / "components" / "agent" / "AgentChat.tsx").read_text(encoding="utf-8")

        self.assertIn("会话已失效", content)
        self.assertIn("setSession(null)", content)

    def test_agent_chat_confirm_submits_pending_message_before_confirming(self):
        content = (ROOT / "src" / "components" / "agent" / "AgentChat.tsx").read_text(encoding="utf-8")

        self.assertIn("const pendingMessage = message.trim();", content)
        self.assertIn(
            "const sessionToConfirm = pendingMessage ? await sendAgentMessage(session.id, pendingMessage) : session;",
            content,
        )
        self.assertIn("const nextSession = await confirmAgentSession(sessionToConfirm.id);", content)
        self.assertIn("setMessage('');", content)

    def test_readme_distinguishes_fixture_smoke_mode_from_real_external_provider_mode(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        lowered = readme.lower()

        self.assertIn("deterministic", readme)
        self.assertIn("fixture", readme)
        self.assertTrue("smoke" in lowered or "冒烟" in readme)
        self.assertTrue("demo" in lowered or "演示" in readme)
        self.assertIn("真实外部", readme)
        self.assertIn("provider", readme)
        self.assertIn("fixture,pexels,youtube", readme)
        self.assertIn("pexels,youtube", readme)

    def test_run_fixture_smoke_script_declares_cli_contract_markers(self):
        script_path = ROOT / "scripts" / "run_fixture_smoke.py"
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("argparse", content)
        self.assertIn("http://127.0.0.1:8010", content)
        self.assertIn("/api/agent/sessions", content)
        self.assertIn("SMOKE OK", content)
        self.assertIn("SMOKE FAILED", content)

    def test_run_fixture_smoke_script_declares_request_and_failure_helpers(self):
        script_path = ROOT / "scripts" / "run_fixture_smoke.py"
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("def request_json(", content)
        self.assertIn("HTTPError", content)
        self.assertIn("URLError", content)
        self.assertIn("def print_failure(", content)
        self.assertIn("api_error", content)
        self.assertIn("timeout", content)
        self.assertIn("job_missing", content)
        self.assertIn("artifact_missing", content)
        self.assertIn("session_id=", content)
        self.assertIn("job_id=", content)
        self.assertIn("video_url=", content)
        self.assertIn("output_path=", content)

    def test_run_fixture_smoke_script_confirms_grounding_before_plan_keyword_update_and_confirm(self):
        script_path = ROOT / "scripts" / "run_fixture_smoke.py"
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("/grounding/confirm", content)
        self.assertIn("candidateIds", content)
        self.assertIn("/messages", content)
        self.assertIn("场景1：城市 黄昏 车流", content)
        self.assertIn("场景2：咖啡 特写 手工艺", content)
        self.assertIn("场景3：海边 日落 风景", content)
        self.assertIn("场景4：雪山 航拍 自然", content)

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
        service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in session.grounding.candidates[:2]],
        )
        service.confirm_session(session.id)

        updated = asyncio.run(service.run_confirmed_session(session.id, fake_search, fake_render))

        self.assertEqual(updated.status, AgentStatus.DONE)
        self.assertEqual(updated.progress, 100)
        self.assertEqual(len(updated.clips), 1)
        self.assertEqual(updated.videoUrl, f"/output/{session.id}.mp4")

    def test_run_confirmed_session_fixture_smoke_exposes_verifiable_video_result_entrypoint(self):
        from backend.models.agent import AgentStatus, ClipInfo
        from backend.services.agent_service import AgentService

        async def fake_search(session_id, scenes):
            return [
                ClipInfo(
                    sceneId=scenes[0].id,
                    sourceUrl="/fixtures/vid_001.mp4",
                    localPath="backend/downloads/session_fixture_1.mp4",
                    publicUrl="/downloads/session_fixture_1.mp4",
                    duration=6,
                )
            ]

        async def fake_render(session_id, clips, output_filename):
            return f"/output/{output_filename}"

        service = AgentService()
        session = service.create_session("用 deterministic fixture smoke 跑一条演示短片")
        service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in session.grounding.candidates[:2]],
        )
        service.confirm_session(session.id)

        updated = asyncio.run(service.run_confirmed_session(session.id, fake_search, fake_render))

        self.assertEqual(updated.status, AgentStatus.DONE)
        self.assertEqual(len(updated.clips), 1)
        self.assertEqual(updated.clips[0].publicUrl, "/downloads/session_fixture_1.mp4")
        self.assertEqual(updated.videoUrl, f"/output/{session.id}.mp4")
        self.assertTrue(updated.videoUrl.startswith("/output/"))
        self.assertTrue(updated.videoUrl.endswith(".mp4"))

    def test_run_confirmed_session_without_downloaded_clips_fails(self):
        from backend.models.agent import AgentStatus
        from backend.services.agent_service import AgentService

        async def fake_search(session_id, scenes):
            return []

        async def fake_render(session_id, clips, output_filename):
            return f"/output/{output_filename}"

        service = AgentService()
        session = service.create_session("做一个科技短片")
        service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in session.grounding.candidates[:2]],
        )
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
        client.post(
            f"/api/agent/sessions/{created['id']}/grounding/confirm",
            json={"candidateIds": [candidate["id"] for candidate in created["grounding"]["candidates"][:2]]},
        )
        response = client.post(f"/api/agent/sessions/{created['id']}/confirm")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "queued")
        self.assertEqual(data["progress"], 25)
        self.assertIn("任务已入队", data["currentStep"])

    def test_confirm_session_api_rejects_non_confirmable_status(self):
        from backend.main import app

        client = _make_test_client(app)
        created = client.post("/api/agent/sessions", json={"message": "做一个科技短片"}).json()
        client.post(
            f"/api/agent/sessions/{created['id']}/grounding/confirm",
            json={"candidateIds": [candidate["id"] for candidate in created["grounding"]["candidates"][:2]]},
        )
        first = client.post(f"/api/agent/sessions/{created['id']}/confirm")
        second = client.post(f"/api/agent/sessions/{created['id']}/confirm")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 400)


if __name__ == "__main__":
    unittest.main()
