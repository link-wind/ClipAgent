import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.api.agent as agent_api_module
from backend.db.base import Base
from backend.db.repositories import (
    AgentArtifactRepository,
    AgentEventRepository,
    AgentJobRepository,
    AgentSessionRepository,
)
from backend.main import app
from backend.app.execution.execution_service import AgentExecutionService
from backend.app.agent.read_service import AgentReadService
from backend.services.agent_service import agent_service
from backend.app.agent.session_service import AgentSessionService
from backend.app.execution.task_read_service import AgentTaskReadService


ROOT = Path(__file__).resolve().parents[1]


class InfrastructureDocsTests(unittest.TestCase):
    def test_docker_compose_includes_postgres_and_redis_services(self):
        compose_path = ROOT / "docker-compose.yml"

        self.assertTrue(compose_path.exists())
        content = compose_path.read_text(encoding="utf-8")

        self.assertIn("postgres:", content)
        self.assertIn("image: postgres:16", content)
        self.assertRegex(content, r'"\$\{POSTGRES_PORT:-5432\}:5432"|"?5432:5432"?')
        self.assertIn("clipforge", content)
        self.assertIn("redis:", content)
        self.assertIn("image: redis:7", content)
        self.assertRegex(content, r'"\$\{REDIS_PORT:-6379\}:6379"|"?6379:6379"?')

    def test_env_example_contains_required_agent_persistence_variables(self):
        env_path = ROOT / ".env.example"

        self.assertTrue(env_path.exists())
        content = env_path.read_text(encoding="utf-8")

        self.assertIn("CLIPFORGE_DATABASE_URL=", content)
        self.assertIn("CLIPFORGE_REDIS_URL=", content)
        self.assertIn("CELERY_BROKER_URL=", content)
        self.assertIn("CELERY_RESULT_BACKEND=", content)

    def test_readme_describes_local_postgres_redis_and_runtime_commands(self):
        readme_path = ROOT / "README.md"

        self.assertTrue(readme_path.exists())
        content = readme_path.read_text(encoding="utf-8")

        self.assertIn("docker compose up -d postgres redis", content)
        self.assertIn("PostgreSQL", content)
        self.assertIn("Redis", content)
        self.assertIn("Celery", content)
        self.assertIn("uvicorn backend.main:app", content)
        self.assertIn("npm run dev", content)
        self.assertIn("docker compose up --build -d", content)
        self.assertIn("docker compose ps", content)
        self.assertIn("worker --pool solo", content)


class AgentApiP0ContractTests(unittest.TestCase):
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
        agent_service.sessions.clear()

    def tearDown(self):
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_agent_api_still_exposes_confirm_endpoint(self):
        from backend.api.agent import router

        paths = {route.path for route in router.routes}
        self.assertIn("/sessions/{session_id}/confirm", paths)
        self.assertIn("/sessions/{session_id}/events", paths)

    def test_agent_dashboard_and_task_response_models_can_be_instantiated(self):
        from backend.models.agent import AgentDashboardSummary, AgentTaskDetail, AgentTaskSummary

        task = AgentTaskSummary(
            id="job-1",
            sessionId="session-1",
            title="AI 笔记产品宣传片",
            status="queued",
            progress=25,
            currentStep="任务已入队",
            createdAt="2026-05-04T12:00:00",
            updatedAt="2026-05-04T12:01:00",
        )
        detail = AgentTaskDetail(
            **task.model_dump(),
            events=[],
            clips=[],
            error=None,
            videoUrl=None,
        )
        dashboard = AgentDashboardSummary(
            totalSessions=1,
            activeTasks=1,
            completedTasks=0,
            failedTasks=0,
            recentTasks=[task],
        )

        self.assertEqual(task.title, "AI 笔记产品宣传片")
        self.assertEqual(detail.id, "job-1")
        self.assertEqual(dashboard.activeTasks, 1)

    def test_agent_step_response_models_can_be_instantiated(self):
        from backend.models.agent import AgentStep, AgentStepError

        step = AgentStep(
            id="understand_request",
            title="理解原始需求",
            description="读取用户原始 prompt，提炼主题、受众、用途和初步意图。",
            status="failed",
            progress=30,
            summary="已读取原始需求",
            result={"originalPrompt": "做一个 30 秒产品宣传片"},
            error=AgentStepError(
                message="规划失败",
                retryable=True,
                retryableStep="finalize_plan",
            ),
            startedAt="2026-05-05T10:00:00",
            finishedAt="2026-05-05T10:01:00",
        )

        self.assertEqual(step.id, "understand_request")
        self.assertEqual(step.error.retryableStep, "finalize_plan")

    def test_agent_api_create_get_and_add_message_round_trip_uses_db_backed_services(self):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                create_response = await client.post("/api/agent/sessions", json={})
                self.assertEqual(create_response.status_code, 200)
                created_session = create_response.json()

                session_id = created_session["id"]
                self.assertEqual(created_session["status"], "idle")
                self.assertEqual(len(created_session["messages"]), 0)
                self.assertIsNone(created_session["plan"])
                self.assertIsNone(created_session["grounding"])

                message_response = await client.post(
                    f"/api/agent/sessions/{session_id}/messages",
                    json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
                )
                self.assertEqual(message_response.status_code, 200)
                awaiting_session = message_response.json()
                self.assertEqual(awaiting_session["grounding"]["status"], "needs_confirmation")

                confirm_response = await client.post(
                    f"/api/agent/sessions/{session_id}/grounding/confirm",
                    json={
                        "candidateIds": [
                            candidate["id"] for candidate in awaiting_session["grounding"]["candidates"][:2]
                        ]
                    },
                )
                self.assertEqual(confirm_response.status_code, 200)
                confirmed_session = confirm_response.json()
                self.assertIsNotNone(confirmed_session["plan"])
                self.assertEqual(confirmed_session["grounding"]["status"], "confirmed")

                get_response = await client.get(f"/api/agent/sessions/{session_id}")
                self.assertEqual(get_response.status_code, 200)
                fetched_session = get_response.json()
                self.assertEqual(fetched_session["id"], session_id)
                self.assertEqual(len(fetched_session["messages"]), 3)
                self.assertEqual(
                    fetched_session["plan"]["title"],
                    confirmed_session["plan"]["title"],
                )

                message_response = await client.post(
                    f"/api/agent/sessions/{session_id}/messages",
                    json={"message": "再加一点品牌感，更商务一点"},
                )
                self.assertEqual(message_response.status_code, 200)
                updated_session = message_response.json()
                self.assertEqual(updated_session["status"], "plan_ready")
                self.assertEqual(updated_session["plan"]["style"], "商务演示风格")
                self.assertEqual(len(updated_session["messages"]), 5)
                self.assertEqual(updated_session["messages"][-1]["role"], "assistant")

        import asyncio

        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ):
            asyncio.run(_run())

    def test_agent_session_response_includes_standard_steps_from_prompt_and_plan(self):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                create_response = await client.post("/api/agent/sessions", json={})
                self.assertEqual(create_response.status_code, 200)
                created = create_response.json()
                message_response = await client.post(
                    f"/api/agent/sessions/{created['id']}/messages",
                    json={"message": "做一个 30 秒 AI 笔记产品宣传片"},
                )
                self.assertEqual(message_response.status_code, 200)
                awaiting = message_response.json()
                confirm_response = await client.post(
                    f"/api/agent/sessions/{created['id']}/grounding/confirm",
                    json={"candidateIds": [candidate["id"] for candidate in awaiting["grounding"]["candidates"][:2]]},
                )
                self.assertEqual(confirm_response.status_code, 200)
                payload = confirm_response.json()

                self.assertEqual(
                    [step["id"] for step in payload["steps"]],
                    [
                        "understand_request",
                        "extract_requirements",
                        "generate_options",
                        "finalize_plan",
                        "create_task",
                        "search_assets",
                        "prepare_assets",
                        "render_video",
                    ],
                )
                understand_step = payload["steps"][0]
                self.assertEqual(understand_step["status"], "succeeded")
                self.assertEqual(understand_step["result"]["originalPrompt"], "做一个 30 秒 AI 笔记产品宣传片")

                finalize_step = payload["steps"][3]
                self.assertEqual(finalize_step["status"], "succeeded")
                self.assertEqual(finalize_step["result"]["title"], payload["plan"]["title"])
                self.assertEqual(len(finalize_step["result"]["scenes"]), len(payload["plan"]["scenes"]))

                self.assertEqual(payload["steps"][4]["status"], "pending")

        import asyncio

        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ):
            asyncio.run(_run())

    def test_grounding_api_response_includes_query_plan_and_assumptions(self):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                create_response = await client.post("/api/agent/sessions", json={})
                self.assertEqual(create_response.status_code, 200)
                created_session = create_response.json()

                message_response = await client.post(
                    f"/api/agent/sessions/{created_session['id']}/messages",
                    json={"message": "给 Notion AI 做一个 30 秒产品亮点视频"},
                )
                self.assertEqual(message_response.status_code, 200)
                awaiting = message_response.json()

                grounding = awaiting["grounding"]
                self.assertIsInstance(grounding["assumptions"], list)
                self.assertTrue(grounding["queryPlan"])
                self.assertTrue(grounding["searchQueries"])
                self.assertEqual(
                    [item["text"] for item in grounding["queryPlan"]],
                    grounding["searchQueries"],
                )

        import asyncio

        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ):
            asyncio.run(_run())

    def test_session_steps_show_candidate_confirmation_before_finalize_plan(self):
        session = self.session_service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        steps = session.steps

        self.assertEqual(steps[0].id, "understand_request")
        self.assertEqual(steps[0].status, "succeeded")
        self.assertEqual(steps[1].id, "extract_requirements")
        self.assertEqual(steps[1].status, "succeeded")
        self.assertEqual(steps[2].id, "generate_options")
        self.assertEqual(steps[2].status, "succeeded")
        self.assertIn("options", steps[2].result)
        self.assertEqual(steps[3].id, "finalize_plan")
        self.assertEqual(steps[3].status, "succeeded")

    def test_confirmed_session_steps_mark_create_task_succeeded(self):
        session = self.session_service.create_session()
        awaiting = self.session_service.add_user_message(session.id, "做一个 30 秒 AI 笔记产品宣传片")
        grounded_session = self.session_service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in awaiting.grounding.candidates[:2]],
        )
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda job_id: None,
        )

        confirmed_session = execution_service.confirm_session(grounded_session.id)

        self.assertEqual(confirmed_session.status.value, "queued")
        self.assertEqual(confirmed_session.steps[4].id, "create_task")
        self.assertEqual(confirmed_session.steps[4].status, "succeeded")
        self.assertEqual(confirmed_session.steps[5].status, "pending")

    def test_confirm_without_plan_marks_finalize_plan_failed_in_session_steps(self):
        session = self.session_service.create_session()
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda job_id: None,
        )

        confirmed_session = execution_service.confirm_session(session.id)

        self.assertEqual(confirmed_session.status.value, "failed")
        self.assertEqual(confirmed_session.steps[3].id, "finalize_plan")
        self.assertEqual(confirmed_session.steps[3].status, "failed")
        self.assertEqual(confirmed_session.steps[3].error.retryableStep, "finalize_plan")
        self.assertEqual(confirmed_session.steps[4].status, "pending")

    def test_session_steps_follow_execution_progress_events(self):
        session = self.session_service.create_session("做一个 30 秒 AI 笔记产品宣传片")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            event_repo = AgentEventRepository(db)
            session_record = session_repo.get(session.id)
            self.assertIsNotNone(session_record)
            assert session_record is not None

            session_record.status = "searching"
            session_record.progress = 35
            session_record.current_step = "正在搜索素材"
            event_repo.create(
                session_id=session.id,
                job_id=None,
                event_type="job_started",
                step="searching",
                progress=35,
                message="任务开始执行",
                payload_json={},
            )
            db.commit()

        searching_session = self.read_service.read_session(session.id)
        self.assertEqual(searching_session.steps[4].status, "succeeded")
        self.assertEqual(searching_session.steps[5].status, "running")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            event_repo = AgentEventRepository(db)
            session_record = session_repo.get(session.id)
            self.assertIsNotNone(session_record)
            assert session_record is not None

            session_record.status = "downloading"
            session_record.progress = 60
            session_record.current_step = "素材已下载，准备渲染"
            event_repo.create(
                session_id=session.id,
                job_id=None,
                event_type="clips_ready",
                step="downloading",
                progress=60,
                message="素材已准备完成，共 4 段",
                payload_json={"clipCount": 4},
            )
            db.commit()

        downloading_session = self.read_service.read_session(session.id)
        self.assertEqual(downloading_session.steps[5].status, "succeeded")
        self.assertEqual(downloading_session.steps[6].status, "running")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            event_repo = AgentEventRepository(db)
            session_record = session_repo.get(session.id)
            self.assertIsNotNone(session_record)
            assert session_record is not None

            session_record.status = "rendering"
            session_record.progress = 80
            session_record.current_step = "正在合成视频"
            event_repo.create(
                session_id=session.id,
                job_id=None,
                event_type="render_started",
                step="rendering",
                progress=80,
                message="开始合成视频",
                payload_json={},
            )
            db.commit()

        rendering_session = self.read_service.read_session(session.id)
        self.assertEqual(rendering_session.steps[6].status, "succeeded")
        self.assertEqual(rendering_session.steps[7].status, "running")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            event_repo = AgentEventRepository(db)
            session_record = session_repo.get(session.id)
            self.assertIsNotNone(session_record)
            assert session_record is not None

            session_record.status = "done"
            session_record.progress = 100
            session_record.current_step = "完成"
            session_record.video_url = "https://cdn.example.com/final-video.mp4"
            event_repo.create(
                session_id=session.id,
                job_id=None,
                event_type="job_succeeded",
                step="done",
                progress=100,
                message="视频已经生成，可以预览或下载。",
                payload_json={"videoUrl": "https://cdn.example.com/final-video.mp4"},
            )
            db.commit()

        done_session = self.read_service.read_session(session.id)
        self.assertEqual(done_session.steps[7].status, "succeeded")
        self.assertEqual(done_session.steps[7].result["videoUrl"], "https://cdn.example.com/final-video.mp4")

    def test_failed_session_steps_map_retryable_standard_step(self):
        session = self.session_service.create_session("做一个 30 秒 AI 笔记产品宣传片")

        with self.session_factory() as db:
            session_repo = AgentSessionRepository(db)
            event_repo = AgentEventRepository(db)
            session_record = session_repo.get(session.id)
            self.assertIsNotNone(session_record)
            assert session_record is not None

            session_record.status = "failed"
            session_record.progress = 35
            session_record.current_step = "处理失败：素材搜索失败"
            session_record.error_message = "素材搜索失败"
            session_record.error_retryable_step = "searching"
            event_repo.create(
                session_id=session.id,
                job_id=None,
                event_type="job_failed",
                step="failed",
                progress=35,
                message="素材搜索失败",
                payload_json={"retryableStep": "searching"},
            )
            db.commit()

        failed_session = self.read_service.read_session(session.id)
        self.assertEqual(failed_session.steps[4].status, "succeeded")
        self.assertEqual(failed_session.steps[5].status, "failed")
        self.assertEqual(failed_session.steps[5].error.retryableStep, "search_assets")
        self.assertEqual(failed_session.steps[6].status, "pending")
        self.assertEqual(failed_session.steps[7].status, "pending")

    def test_failed_search_replan_keeps_session_in_queued_state_with_new_active_job(self):
        from backend.tasks.agent_tasks import run_agent_job

        session = self.session_service.create_session("做一个智能剪辑 agent 演示视频")
        execution_service = AgentExecutionService(
            session_factory=self.session_factory,
            enqueue_job=lambda _job_id: None,
        )
        confirmed_session = execution_service.confirm_session(session.id)

        async def failing_search_runner(_session_id, _scenes):
            raise RuntimeError("素材检索失败")

        with patch("backend.tasks.agent_tasks.SessionLocal", self.session_factory), patch(
            "backend.tasks.agent_tasks.search_and_download_agent_clips",
            failing_search_runner,
        ):
            run_agent_job(confirmed_session.activeJobId)

        reloaded = self.read_service.read_session(session.id)
        self.assertEqual(reloaded.status.value, "queued")
        self.assertEqual(reloaded.currentStep, "任务已重新规划并重新入队")
        self.assertIsNotNone(reloaded.activeJobId)
        self.assertNotEqual(reloaded.activeJobId, confirmed_session.activeJobId)

    def test_agent_event_history_endpoint_returns_persisted_events(self):
        async def _run():
            session = self.session_service.create_session("做一个可恢复的智能剪辑任务")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="queued",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_queued",
                    step="queued",
                    progress=25,
                    message="任务已入队，等待执行",
                    payload_json={"jobId": job_record.id, "source": "test"},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(f"/api/agent/sessions/{session.id}/events")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(len(payload), 1)
                self.assertEqual(payload[0]["eventType"], "job_queued")
                self.assertEqual(payload[0]["step"], "queued")
                self.assertEqual(payload[0]["progress"], 25)
                self.assertEqual(payload[0]["message"], "任务已入队，等待执行")
                self.assertEqual(payload[0]["payload"]["source"], "test")
                self.assertEqual(payload[0]["payload"]["jobId"], job_id)

        import asyncio

        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ):
            asyncio.run(_run())

    def test_agent_dashboard_task_list_and_detail_endpoints_return_persisted_jobs(self):
        async def _run():
            session = self.session_service.create_session("做一个 30 秒产品宣传片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="queued",
                    progress=25,
                    current_step="任务已入队",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_queued",
                    step="queued",
                    progress=25,
                    message="任务已入队，等待执行",
                    payload_json={"jobId": job_record.id, "source": "test"},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                dashboard_response = await client.get("/api/agent/dashboard")
                self.assertEqual(dashboard_response.status_code, 200)
                dashboard_payload = dashboard_response.json()
                self.assertEqual(dashboard_payload["totalSessions"], 1)
                self.assertEqual(dashboard_payload["activeTasks"], 1)
                self.assertEqual(dashboard_payload["recentTasks"][0]["id"], job_id)

                tasks_response = await client.get("/api/agent/tasks")
                self.assertEqual(tasks_response.status_code, 200)
                tasks_payload = tasks_response.json()
                self.assertEqual(len(tasks_payload), 1)
                self.assertEqual(tasks_payload[0]["id"], job_id)
                self.assertEqual(tasks_payload[0]["sessionId"], session.id)
                self.assertEqual(tasks_payload[0]["status"], "queued")

                detail_response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail_payload = detail_response.json()
                self.assertEqual(detail_payload["id"], job_id)
                self.assertEqual(detail_payload["events"][0]["eventType"], "job_queued")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ), patch.object(agent_api_module, "task_read_service", task_read_service):
            asyncio.run(_run())

    def test_agent_task_detail_endpoint_returns_404_for_missing_job(self):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/agent/tasks/job-missing")
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json()["detail"], "Task not found")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "task_read_service", task_read_service):
            asyncio.run(_run())

    def test_agent_task_detail_response_includes_standard_steps_and_current_step_id(self):
        async def _run():
            session = self.session_service.create_session("做一个产品宣传片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                artifact_repo = AgentArtifactRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="running",
                    progress=80,
                    current_step="正在合成视频",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_started",
                    step="searching",
                    progress=35,
                    message="任务开始执行",
                    payload_json={"jobId": job_record.id},
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="clips_ready",
                    step="downloading",
                    progress=60,
                    message="素材已准备完成，共 1 段",
                    payload_json={"clipCount": 1},
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="render_started",
                    step="rendering",
                    progress=80,
                    message="开始合成视频",
                    payload_json={},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    artifact_type="clip",
                    scene_id="1",
                    source_url="https://example.com/source.mp4",
                    local_path="/tmp/clip.mp4",
                    public_url="https://cdn.example.com/clip.mp4",
                    duration=6.0,
                    metadata_json={"caption": "clip", "trimStart": 1.0, "trimDuration": 5.0},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                tasks_response = await client.get("/api/agent/tasks")
                self.assertEqual(tasks_response.status_code, 200)
                task_summary = tasks_response.json()[0]
                self.assertEqual(task_summary["currentStepId"], "render_video")

                detail_response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail = detail_response.json()

                self.assertEqual(len(detail["steps"]), 8)
                self.assertEqual(detail["steps"][4]["id"], "create_task")
                self.assertEqual(detail["steps"][4]["status"], "succeeded")
                self.assertEqual(detail["steps"][6]["id"], "prepare_assets")
                self.assertEqual(detail["steps"][6]["status"], "succeeded")
                self.assertEqual(detail["steps"][6]["result"]["clips"][0]["publicUrl"], "https://cdn.example.com/clip.mp4")
                self.assertEqual(detail["steps"][7]["id"], "render_video")
                self.assertEqual(detail["steps"][7]["status"], "running")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_task_succeeded_detail_keeps_render_video_succeeded(self):
        async def _run():
            session = self.session_service.create_session("做一个产品宣传片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                artifact_repo = AgentArtifactRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="succeeded",
                    progress=100,
                    current_step="完成",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_succeeded",
                    step="done",
                    progress=100,
                    message="视频已经生成，可以预览或下载。",
                    payload_json={"videoUrl": "https://cdn.example.com/final-video.mp4"},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    artifact_type="video",
                    public_url="https://cdn.example.com/final-video.mp4",
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                detail_response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail = detail_response.json()

                self.assertEqual(detail["steps"][7]["id"], "render_video")
                self.assertEqual(detail["steps"][7]["status"], "succeeded")
                self.assertEqual(detail["steps"][7]["result"]["videoUrl"], "https://cdn.example.com/final-video.mp4")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_task_failed_detail_keeps_failed_render_video_step(self):
        async def _run():
            session = self.session_service.create_session("做一个产品宣传片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="failed",
                    progress=80,
                    current_step="处理失败：渲染服务不可用",
                    error_message="渲染服务不可用",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_failed",
                    step="failed",
                    progress=80,
                    message="渲染服务不可用",
                    payload_json={"retryableStep": "rendering"},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                detail_response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(detail_response.status_code, 200)
                detail = detail_response.json()

                self.assertEqual(detail["steps"][7]["id"], "render_video")
                self.assertEqual(detail["steps"][7]["status"], "failed")
                self.assertEqual(detail["steps"][7]["error"]["retryableStep"], "render_video")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_task_failed_retryable_step_maps_to_standard_step_error(self):
        async def _run():
            session = self.session_service.create_session("做一个失败可恢复的短片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="failed",
                    progress=60,
                    current_step="处理失败：下载素材失败",
                    error_message="下载素材失败",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_failed",
                    step="failed",
                    progress=60,
                    message="下载素材失败",
                    payload_json={"retryableStep": "downloading"},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(f"/api/agent/tasks/{job_id}")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                failed_steps = [step for step in payload["steps"] if step["status"] == "failed"]
                self.assertEqual(len(failed_steps), 1)
                self.assertEqual(failed_steps[0]["id"], "prepare_assets")
                self.assertEqual(failed_steps[0]["error"]["message"], "下载素材失败")
                self.assertTrue(failed_steps[0]["error"]["retryable"])
                self.assertEqual(failed_steps[0]["error"]["retryableStep"], "prepare_assets")
                self.assertEqual(payload["steps"][7]["status"], "pending")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_task_failed_summary_uses_retryable_step_as_current_step_id(self):
        async def _run():
            session = self.session_service.create_session("做一个素材搜索失败的短片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="failed",
                    progress=35,
                    current_step="处理失败：没有下载到可用素材",
                    error_message="没有下载到可用素材",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_failed",
                    step="failed",
                    progress=35,
                    message="没有下载到可用素材",
                    payload_json={"retryableStep": "searching"},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/agent/tasks")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(payload[0]["id"], job_id)
                self.assertEqual(payload[0]["currentStepId"], "search_assets")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_dashboard_failed_summary_uses_retryable_step_as_current_step_id(self):
        async def _run():
            session = self.session_service.create_session("做一个素材搜索失败的短片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                event_repo = AgentEventRepository(db)
                job_record = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="failed",
                    progress=35,
                    current_step="处理失败：没有下载到可用素材",
                    error_message="没有下载到可用素材",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=job_record.id,
                    event_type="job_failed",
                    step="failed",
                    progress=35,
                    message="没有下载到可用素材",
                    payload_json={"retryableStep": "searching"},
                )
                job_id = job_record.id
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/agent/dashboard")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(payload["recentTasks"][0]["id"], job_id)
                self.assertEqual(payload["recentTasks"][0]["currentStepId"], "search_assets")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_task_steps_are_isolated_from_other_jobs_in_same_session(self):
        async def _run():
            session = self.session_service.create_session("做一个多阶段短片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                artifact_repo = AgentArtifactRepository(db)
                event_repo = AgentEventRepository(db)

                first_job = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="succeeded",
                    progress=100,
                    current_step="完成",
                )
                second_job = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="rendering",
                    progress=80,
                    current_step="正在合成视频",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=first_job.id,
                    event_type="job_succeeded",
                    step="done",
                    progress=100,
                    message="首个任务完成",
                    payload_json={"videoUrl": "https://cdn.example.com/first-job-video.mp4"},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=first_job.id,
                    artifact_type="video",
                    public_url="https://cdn.example.com/first-job-video.mp4",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=second_job.id,
                    event_type="render_started",
                    step="rendering",
                    progress=80,
                    message="开始合成视频",
                    payload_json={},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=second_job.id,
                    artifact_type="video",
                    public_url="https://cdn.example.com/second-job-video.mp4",
                )
                db.commit()
                first_job_id = first_job.id

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(f"/api/agent/tasks/{first_job_id}")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(payload["steps"][7]["status"], "succeeded")
                self.assertEqual(payload["steps"][7]["result"]["videoUrl"], "https://cdn.example.com/first-job-video.mp4")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_dashboard_counts_are_not_limited_by_recent_tasks_window(self):
        async def _run():
            sessions: list[str] = []
            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                for index in range(55):
                    session = self.session_service.create_session(f"任务 {index}")
                    sessions.append(session.id)
                    status = "running" if index < 30 else "succeeded" if index < 45 else "failed"
                    current_step = "处理中" if status == "running" else "已完成" if status == "succeeded" else "执行失败"
                    job_repo.create(
                        session_id=session.id,
                        plan_id=None,
                        job_type="generate_video",
                        status=status,
                        progress=50 if status == "running" else 100 if status == "succeeded" else 0,
                        current_step=current_step,
                    )
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/agent/dashboard")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(payload["totalSessions"], 55)
                self.assertEqual(payload["activeTasks"], 30)
                self.assertEqual(payload["completedTasks"], 15)
                self.assertEqual(payload["failedTasks"], 10)
                self.assertEqual(len(payload["recentTasks"]), 50)

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_task_detail_isolated_to_requested_job_within_same_session(self):
        async def _run():
            session = self.session_service.create_session("做一个多阶段短片")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                artifact_repo = AgentArtifactRepository(db)
                event_repo = AgentEventRepository(db)

                first_job = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="succeeded",
                    progress=100,
                    current_step="已完成",
                    error_message="旧任务失败信息不该串进来",
                )
                second_job = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="failed",
                    progress=20,
                    current_step="处理失败：渲染服务不可用",
                    error_message="渲染服务不可用",
                )
                second_job_id = second_job.id

                session_record = AgentSessionRepository(db).get(session.id)
                session_record.video_url = "https://cdn.example.com/final-video-from-old-job.mp4"
                session_record.error_retryable_step = "searching"

                artifact_repo.create(
                    session_id=session.id,
                    job_id=first_job.id,
                    artifact_type="clip",
                    scene_id="1",
                    source_url="https://example.com/source-1.mp4",
                    local_path="/tmp/clip-1.mp4",
                    public_url="https://cdn.example.com/clip-1.mp4",
                    duration=3.0,
                    metadata_json={"caption": "clip 1"},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=second_job.id,
                    artifact_type="clip",
                    scene_id="2",
                    source_url="https://example.com/source-2.mp4",
                    local_path="/tmp/clip-2.mp4",
                    public_url="https://cdn.example.com/clip-2.mp4",
                    duration=5.0,
                    metadata_json={"caption": "clip 2"},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=first_job.id,
                    artifact_type="video",
                    public_url="https://cdn.example.com/final-video-from-old-job.mp4",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=first_job.id,
                    event_type="job_succeeded",
                    step="done",
                    progress=100,
                    message="首个任务完成",
                    payload_json={
                        "jobId": first_job.id,
                        "videoUrl": "https://cdn.example.com/final-video-from-old-job.mp4",
                    },
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=second_job.id,
                    event_type="job_failed",
                    step="failed",
                    progress=20,
                    message="第二个任务失败",
                    payload_json={"jobId": second_job.id, "retryableStep": "rendering"},
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=second_job.id,
                    event_type="render_started",
                    step="rendering",
                    progress=80,
                    message="开始合成视频",
                    payload_json={"videoUrl": "https://cdn.example.com/final-video-from-current-job.mp4"},
                )
                artifact_repo.create(
                    session_id=session.id,
                    job_id=second_job.id,
                    artifact_type="video",
                    public_url="https://cdn.example.com/final-video-from-current-job.mp4",
                )
                db.commit()

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(f"/api/agent/tasks/{second_job_id}")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(payload["id"], second_job_id)
                self.assertEqual(len(payload["events"]), 2)
                self.assertEqual(
                    {event["eventType"] for event in payload["events"]},
                    {"job_failed", "render_started"},
                )
                self.assertEqual(len(payload["clips"]), 1)
                self.assertEqual(payload["clips"][0]["caption"], "clip 2")
                self.assertEqual(payload["videoUrl"], "https://cdn.example.com/final-video-from-current-job.mp4")
                self.assertEqual(payload["error"]["retryableStep"], "rendering")

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())

    def test_agent_task_detail_does_not_fallback_to_session_level_video_or_retryable_step(self):
        async def _run():
            session = self.session_service.create_session("做一个不会串值的任务")

            with self.session_factory() as db:
                job_repo = AgentJobRepository(db)
                artifact_repo = AgentArtifactRepository(db)
                event_repo = AgentEventRepository(db)
                session_repo = AgentSessionRepository(db)

                old_job = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="succeeded",
                    progress=100,
                    current_step="已完成",
                )
                current_job = job_repo.create(
                    session_id=session.id,
                    plan_id=None,
                    job_type="generate_video",
                    status="failed",
                    progress=20,
                    current_step="处理失败：网络波动",
                    error_message="网络波动",
                )

                session_record = session_repo.get(session.id)
                session_record.video_url = "https://cdn.example.com/stale-session-video.mp4"
                session_record.error_retryable_step = "searching"

                artifact_repo.create(
                    session_id=session.id,
                    job_id=old_job.id,
                    artifact_type="video",
                    public_url="https://cdn.example.com/old-job-video.mp4",
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=old_job.id,
                    event_type="job_succeeded",
                    step="done",
                    progress=100,
                    message="旧任务完成",
                    payload_json={"videoUrl": "https://cdn.example.com/old-job-video.mp4"},
                )
                event_repo.create(
                    session_id=session.id,
                    job_id=current_job.id,
                    event_type="job_failed",
                    step="failed",
                    progress=20,
                    message="当前任务失败",
                    payload_json={"jobId": current_job.id},
                )
                db.commit()
                current_job_id = current_job.id

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get(f"/api/agent/tasks/{current_job_id}")
                self.assertEqual(response.status_code, 200)
                payload = response.json()

                self.assertEqual(payload["id"], current_job_id)
                self.assertIsNone(payload["videoUrl"])
                self.assertEqual(payload["error"]["message"], "网络波动")
                self.assertIsNone(payload["error"]["retryableStep"])

        import asyncio

        task_read_service = AgentTaskReadService(session_factory=self.session_factory)
        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module, "task_read_service", task_read_service
        ):
            asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
