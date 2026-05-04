import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.api.agent as agent_api_module
from backend.db.base import Base
from backend.db.repositories import AgentEventRepository, AgentJobRepository
from backend.main import app
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_service import agent_service
from backend.services.agent_session_service import AgentSessionService
from backend.services.agent_task_read_service import AgentTaskReadService


ROOT = Path(__file__).resolve().parents[1]


class InfrastructureDocsTests(unittest.TestCase):
    def test_docker_compose_includes_postgres_and_redis_services(self):
        compose_path = ROOT / "docker-compose.yml"

        self.assertTrue(compose_path.exists())
        content = compose_path.read_text(encoding="utf-8")

        self.assertIn("postgres:", content)
        self.assertIn("image: postgres:16", content)
        self.assertIn("5432:5432", content)
        self.assertIn("clipforge", content)
        self.assertIn("redis:", content)
        self.assertIn("image: redis:7", content)
        self.assertIn("6379:6379", content)

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
        self.assertIn("只容器化 PostgreSQL 和 Redis", content)
        self.assertIn("现在会真实投递 Celery 任务", content)
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

    def test_agent_api_create_get_and_add_message_round_trip_uses_db_backed_services(self):
        async def _run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                create_response = await client.post(
                    "/api/agent/sessions",
                    json={"message": "做一个 30 秒的科技产品短片"},
                )
                self.assertEqual(create_response.status_code, 200)
                created_session = create_response.json()

                session_id = created_session["id"]
                self.assertEqual(created_session["status"], "plan_ready")
                self.assertEqual(len(created_session["messages"]), 2)
                self.assertIsNotNone(created_session["plan"])

                get_response = await client.get(f"/api/agent/sessions/{session_id}")
                self.assertEqual(get_response.status_code, 200)
                fetched_session = get_response.json()
                self.assertEqual(fetched_session["id"], session_id)
                self.assertEqual(len(fetched_session["messages"]), 2)
                self.assertEqual(
                    fetched_session["plan"]["title"],
                    created_session["plan"]["title"],
                )

                message_response = await client.post(
                    f"/api/agent/sessions/{session_id}/messages",
                    json={"message": "再加一点品牌感"},
                )
                self.assertEqual(message_response.status_code, 200)
                updated_session = message_response.json()
                self.assertEqual(updated_session["status"], "plan_ready")
                self.assertEqual(len(updated_session["messages"]), 4)
                self.assertEqual(updated_session["messages"][-1]["role"], "assistant")

        import asyncio

        with patch.object(agent_api_module, "session_service", self.session_service), patch.object(
            agent_api_module,
            "read_service",
            self.read_service,
        ):
            asyncio.run(_run())

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


if __name__ == "__main__":
    unittest.main()
