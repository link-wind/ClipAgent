from datetime import datetime
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
import backend.db.models  # noqa: F401
from backend.db.models import (
    AgentRunRecord,
    AgentSessionRecord,
    AgentStepRecord,
    AgentTraceEventRecord,
)
from backend.db.repositories import (
    AgentJobRepository,
    AgentRunRepository,
    AgentSessionRepository,
    AgentStepRepository,
    AgentTraceEventRepository,
)
from backend.models.agent import AgentStep
from backend.models.agent import AgentRunSummary, AgentTraceEvent as AgentTraceEventModel
from backend.domain.skills.contracts import PlannerRequest, SkillRunSummary, SkillSelection
from backend.runtime.skill_engine import PlannerRequestBuildResult
from backend.runtime.trace_recorder import TraceEvent, TraceRecorder
from backend.services.agent_execution_service import AgentExecutionService
from backend.services.agent_read_service import AgentReadService
from backend.services.agent_run_service import ActiveOperationConflict, AgentRunService
from backend.services.agent_session_service import AgentSessionService
from backend.services.agent_step_service import AgentStepService
from backend.services.planner_orchestrator import PlannerOrchestrator


class AgentRunTraceModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_models_define_run_step_trace_tables_and_session_active_operation_fields(self):
        self.assertEqual(AgentRunRecord.__tablename__, "agent_runs")
        self.assertEqual(AgentStepRecord.__tablename__, "agent_steps")
        self.assertEqual(AgentTraceEventRecord.__tablename__, "agent_trace_events")

        self.assert_model_columns(
            AgentRunRecord,
            {
                "id",
                "session_id",
                "source_message_id",
                "trigger_type",
                "status",
                "summary",
                "error_message",
                "parent_run_id",
                "related_job_id",
                "actor_type",
                "actor_role",
                "actor_id",
                "agent_name",
                "input_json",
                "output_json",
                "metadata_json",
                "started_at",
                "finished_at",
                "created_at",
                "updated_at",
            },
        )
        self.assert_model_columns(
            AgentStepRecord,
            {
                "id",
                "session_id",
                "run_id",
                "job_id",
                "step_key",
                "title",
                "description",
                "status",
                "progress",
                "summary",
                "result_json",
                "error_json",
                "sequence",
                "actor_type",
                "actor_role",
                "actor_id",
                "agent_name",
                "started_at",
                "finished_at",
                "created_at",
                "updated_at",
            },
        )
        self.assert_model_columns(
            AgentTraceEventRecord,
            {
                "id",
                "session_id",
                "run_id",
                "step_id",
                "job_id",
                "event_type",
                "level",
                "message",
                "payload_json",
                "sequence",
                "actor_type",
                "actor_role",
                "actor_id",
                "agent_name",
                "created_at",
            },
        )
        self.assert_model_columns(
            AgentSessionRecord,
            {"active_operation_type", "active_operation_id"},
        )

    def assert_model_columns(self, model, expected_columns):
        self.assertTrue(
            expected_columns.issubset(set(model.__table__.columns.keys())),
            expected_columns - set(model.__table__.columns.keys()),
        )

    def test_session_repository_guards_active_operation_lifecycle(self):
        session_repo = AgentSessionRepository(self.db)
        session = session_repo.create(title="operation guard")
        self.db.commit()

        self.assertEqual(session.active_operation_type, "none")
        self.assertIsNone(session.active_operation_id)

        started = session_repo.try_start_operation(
            session.id,
            "run",
            "run-1",
        )
        self.db.commit()

        self.assertTrue(started)
        self.assertEqual(session_repo.get(session.id).active_operation_type, "run")
        self.assertEqual(session_repo.get(session.id).active_operation_id, "run-1")

        overlapping = session_repo.try_start_operation(
            session.id,
            "job",
            "job-1",
        )
        self.assertFalse(overlapping)

        wrong_finish = session_repo.finish_operation(
            session.id,
            "run",
            "run-other",
        )
        self.assertFalse(wrong_finish)
        self.assertEqual(session_repo.get(session.id).active_operation_id, "run-1")

        finished = session_repo.finish_operation(
            session.id,
            "run",
            "run-1",
        )
        self.db.commit()
        self.assertTrue(finished)
        self.assertEqual(session_repo.get(session.id).active_operation_type, "none")
        self.assertIsNone(session_repo.get(session.id).active_operation_id)

        restarted = session_repo.try_start_operation(
            session.id,
            "trace",
            "trace-1",
        )
        self.assertTrue(restarted)
        failed = session_repo.fail_operation(
            session.id,
            "trace",
            "trace-1",
            error_message="trace failed",
        )
        self.db.commit()

        failed_session = session_repo.get(session.id)
        self.assertTrue(failed)
        self.assertEqual(failed_session.active_operation_type, "none")
        self.assertIsNone(failed_session.active_operation_id)
        self.assertEqual(failed_session.status, "failed")
        self.assertEqual(failed_session.error_message, "trace failed")

    def test_session_repository_rejects_stale_concurrent_operation_start(self):
        session_repo = AgentSessionRepository(self.db)
        session = session_repo.create(title="operation race")
        self.db.commit()

        stale_db = self.SessionLocal()
        try:
            stale_repo = AgentSessionRepository(stale_db)
            stale_record = stale_repo.get(session.id)
            self.assertEqual(stale_record.active_operation_type, "none")

            self.assertTrue(session_repo.try_start_operation(session.id, "run", "run-1"))
            self.db.commit()

            self.assertFalse(stale_repo.try_start_operation(session.id, "job", "job-1"))
            stale_db.rollback()
            self.db.expire_all()
            current_session = session_repo.get(session.id)
            self.assertEqual(current_session.active_operation_type, "run")
            self.assertEqual(current_session.active_operation_id, "run-1")
        finally:
            stale_db.close()

    def test_run_step_and_trace_repositories_create_get_list_with_stable_ordering(self):
        session_repo = AgentSessionRepository(self.db)
        run_repo = AgentRunRepository(self.db)
        step_repo = AgentStepRepository(self.db)
        trace_repo = AgentTraceEventRepository(self.db)

        session = session_repo.create(title="trace storage")
        other_session = session_repo.create(title="other")
        self.db.commit()

        run_b = run_repo.create(
            id="run-b",
            session_id=session.id,
            trigger_type="manual",
            status="running",
            input_json=None,
            output_json=None,
            metadata_json=None,
        )
        run_a = run_repo.create(
            id="run-a",
            session_id=session.id,
            trigger_type="retry",
            status="pending",
        )
        run_repo.create(
            id="run-other",
            session_id=other_session.id,
            trigger_type="manual",
            status="running",
        )
        run_a.created_at = run_b.created_at
        run_b.created_at = run_b.created_at
        self.db.flush()
        self.db.commit()

        self.assertEqual(run_repo.get("run-a").trigger_type, "retry")
        self.assertEqual(run_b.input_json, {})
        self.assertEqual(run_b.output_json, {})
        self.assertEqual(run_b.metadata_json, {})
        self.assertEqual(
            [run.id for run in run_repo.list_for_session(session.id)],
            ["run-a", "run-b"],
        )
        updated_run = run_repo.update_status(
            "run-a",
            status="succeeded",
            summary="done",
            output_json={"planId": "plan-1"},
        )
        self.assertEqual(updated_run.status, "succeeded")
        self.assertEqual(updated_run.summary, "done")
        self.assertEqual(updated_run.output_json, {"planId": "plan-1"})

        step_second = step_repo.create(
            id="step-second",
            session_id=session.id,
            run_id=run_a.id,
            step_key="render",
            title="Render",
            status="pending",
            sequence=2,
            result_json=None,
            error_json=None,
        )
        step_first = step_repo.create(
            id="step-first",
            session_id=session.id,
            run_id=run_a.id,
            step_key="search",
            title="Search",
            status="running",
            sequence=1,
        )
        step_repo.create(
            id="step-other-run",
            session_id=session.id,
            run_id=run_b.id,
            step_key="other",
            title="Other",
            status="pending",
            sequence=1,
        )
        self.db.commit()

        self.assertEqual(step_repo.get("step-first").step_key, "search")
        self.assertIsNone(step_second.result_json)
        self.assertIsNone(step_second.error_json)
        self.assertEqual(
            [step.id for step in step_repo.list_for_run(run_a.id)],
            ["step-first", "step-second"],
        )
        self.assertEqual(
            [step.id for step in step_repo.list_for_session(session.id)],
            ["step-first", "step-other-run", "step-second"],
        )
        job = AgentJobRepository(self.db).create(
            session_id=session.id,
            job_type="generate_video",
            status="queued",
        )
        job_step = step_repo.create(
            id="step-job",
            session_id=session.id,
            job_id=job.id,
            step_key="render_video",
            title="Render",
            status="running",
            sequence=8,
        )
        self.assertEqual(step_repo.get_for_job_step(job.id, "render_video").id, job_step.id)
        updated_step = step_repo.update_status(
            job_step.id,
            status="succeeded",
            progress=100,
            summary="rendered",
            result_json={"videoUrl": "/output/demo.mp4"},
        )
        self.assertEqual(updated_step.status, "succeeded")
        self.assertEqual(updated_step.progress, 100)
        self.assertEqual(updated_step.result_json, {"videoUrl": "/output/demo.mp4"})

        trace_second = trace_repo.create(
            id="trace-second",
            session_id=session.id,
            run_id=run_a.id,
            step_id=step_first.id,
            event_type="step.completed",
            level="info",
            message="done",
            payload_json=None,
        )
        trace_first = trace_repo.create(
            id="trace-first",
            session_id=session.id,
            run_id=run_a.id,
            step_id=step_first.id,
            event_type="step.started",
            level="debug",
            message="start",
        )
        trace_repo.create(
            id="trace-other-session",
            session_id=other_session.id,
            event_type="session.started",
            level="info",
            message="other",
        )
        self.db.commit()

        self.assertEqual(trace_repo.get("trace-first").event_type, "step.started")
        self.assertEqual(trace_second.payload_json, {})
        self.assertEqual(trace_second.sequence, 1)
        self.assertEqual(trace_first.sequence, 2)
        self.assertEqual(
            [trace.id for trace in trace_repo.list_for_session(session.id)],
            ["trace-second", "trace-first"],
        )
        self.assertEqual(
            [trace.id for trace in trace_repo.list_for_run(run_a.id)],
            ["trace-second", "trace-first"],
        )
        self.assertEqual(
            [trace.id for trace in trace_repo.list_for_step(step_first.id)],
            ["trace-second", "trace-first"],
        )
        self.assertEqual(
            [trace.id for trace in trace_repo.list_for_session(session.id, after_sequence=1, limit=1)],
            ["trace-first"],
        )

    def test_run_service_manages_run_lifecycle_and_active_operation(self):
        session_repo = AgentSessionRepository(self.db)
        session = session_repo.create(status="idle", current_step="", progress=0)
        service = AgentRunService(self.db)

        run = service.start_run(session.id, trigger_type="user_message")
        self.assertEqual(run.status, "running")
        self.assertEqual(session_repo.get(session.id).active_operation_type, "run")
        self.assertEqual(session_repo.get(session.id).active_operation_id, run.id)

        with self.assertRaises(ActiveOperationConflict) as conflict:
            service.start_run(session.id, trigger_type="user_revision")
        self.assertEqual(conflict.exception.operation_type, "run")
        self.assertEqual(conflict.exception.operation_id, run.id)

        completed = service.succeed_run(run.id, summary="方案已生成", output={"planId": "plan-1"})
        self.assertEqual(completed.status, "succeeded")
        self.assertEqual(completed.summary, "方案已生成")
        self.assertEqual(completed.output_json, {"planId": "plan-1"})
        self.assertEqual(session_repo.get(session.id).active_operation_type, "none")

        trace_events = AgentTraceEventRepository(self.db).list_for_run(run.id)
        self.assertEqual([event.event_type for event in trace_events], ["run_started", "run_succeeded"])

    def test_step_service_updates_step_and_trace(self):
        session = AgentSessionRepository(self.db).create(status="idle", current_step="", progress=0)
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="user_message",
            status="running",
        )
        service = AgentStepService(self.db)

        step = service.start_step(
            session_id=session.id,
            run_id=run.id,
            step_key="finalize_plan",
            title="生成最终执行方案",
            description="生成最终方案、镜头拆分和可确认计划。",
            sequence=4,
        )
        completed = service.succeed_step(step.id, summary="已生成方案", result={"title": "Demo"})
        api_step = service.to_api_step(completed)

        self.assertIsInstance(api_step, AgentStep)
        self.assertEqual(api_step.id, "finalize_plan")
        self.assertEqual(api_step.status, "succeeded")
        self.assertEqual(api_step.progress, 100)
        self.assertEqual(api_step.result, {"title": "Demo"})
        self.assertIsNotNone(api_step.startedAt)
        self.assertIsNotNone(api_step.finishedAt)
        self.assertEqual(
            [event.event_type for event in AgentTraceEventRepository(self.db).list_for_run(run.id)],
            ["step_started", "step_succeeded"],
        )

    def test_step_service_accepts_skill_observability_step_keys(self):
        session = AgentSessionRepository(self.db).create(status="idle", current_step="", progress=0)
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="user_message",
            status="running",
        )
        service = AgentStepService(self.db)

        first = service.start_step(
            session_id=session.id,
            run_id=run.id,
            step_key="select_strategy",
            title="选择规划策略",
            description="选择 skill。",
            sequence=1,
        )
        second = service.start_step(
            session_id=session.id,
            run_id=run.id,
            step_key="build_planner_request",
            title="构建 Planner Request",
            description="生成 planner request 证据。",
            sequence=2,
        )

        self.assertEqual(
            [step.step_key for step in AgentStepRepository(self.db).list_for_run(run.id)],
            ["select_strategy", "build_planner_request"],
        )
        self.assertEqual(first.status, "running")
        self.assertEqual(second.status, "running")

    def test_planner_orchestrator_builds_planner_request_through_skill_engine(self):
        class FakeSkillEngine:
            def __init__(self):
                self.selection_requests = []
                self.build_requests = []

            def select_skill(self, request):
                self.selection_requests.append(request)
                return SkillSelection(
                    skill_id="builtin.product_intro_video",
                    version="0.1.0",
                    reason="fake selection",
                )

            def build_planner_request(self, request, *, selection=None):
                self.build_requests.append((request, selection))
                return PlannerRequestBuildResult(
                    selection=selection,
                    planner_request=PlannerRequest(
                        action=request.run_type,
                        system_prompt="fake prompt",
                        messages=[{"role": "user", "content": request.user_message}],
                        output_schema={"type": "agent_plan"},
                    ),
                    summary=SkillRunSummary(
                        skill_id="builtin.product_intro_video",
                        skill_version="0.1.0",
                        status="succeeded",
                    ),
                )

        class FailingRegistry:
            def resolve_handler(self, _skill_id):
                raise AssertionError("planner orchestrator must use SkillEngine.build_planner_request")

        session = AgentSessionRepository(self.db).create(status="idle", current_step="", progress=0)
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="user_message",
            status="running",
        )
        skill_engine = FakeSkillEngine()
        orchestrator = PlannerOrchestrator(
            skill_engine=skill_engine,
            skill_registry=FailingRegistry(),
        )

        orchestrator._record_skill_observability(
            db=self.db,
            session_record=session,
            run_id=run.id,
            run_type="initial_planning",
            user_message="做一个产品介绍视频",
        )

        self.assertEqual(len(skill_engine.selection_requests), 1)
        self.assertEqual(len(skill_engine.build_requests), 1)
        build_request, build_selection = skill_engine.build_requests[0]
        self.assertEqual(build_request.run_type, "initial_planning")
        self.assertEqual(build_selection.skill_id, "builtin.product_intro_video")
        run_record = AgentRunRepository(self.db).get(run.id)
        self.assertEqual(run_record.output_json["plannerRequest"]["action"], "initial_planning")
        self.assertEqual(run_record.metadata_json["skill"]["status"], "succeeded")

    def test_planner_orchestrator_records_skill_engine_build_failure_summary(self):
        class FailingSkillEngine:
            def select_skill(self, _request):
                return SkillSelection(
                    skill_id="builtin.product_intro_video",
                    version="0.1.0",
                    reason="fake selection",
                )

            def build_planner_request(self, _request, *, selection=None):
                return PlannerRequestBuildResult(
                    selection=selection,
                    planner_request=None,
                    summary=SkillRunSummary(
                        skill_id="builtin.product_intro_video",
                        skill_version="0.1.0",
                        status="failed",
                        input_summary="run_type=initial_planning",
                        error_message="handler import failed",
                    ),
                )

        session = AgentSessionRepository(self.db).create(status="idle", current_step="", progress=0)
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="user_message",
            status="running",
        )
        orchestrator = PlannerOrchestrator(skill_engine=FailingSkillEngine())

        with self.assertRaisesRegex(RuntimeError, "handler import failed"):
            orchestrator._record_skill_observability(
                db=self.db,
                session_record=session,
                run_id=run.id,
                run_type="initial_planning",
                user_message="做一个产品介绍视频",
            )

        steps = AgentStepRepository(self.db).list_for_run(run.id)
        events = AgentTraceEventRepository(self.db).list_for_run(run.id)
        failed_event = events[-1]
        run_record = AgentRunRepository(self.db).get(run.id)

        self.assertEqual(steps[-1].step_key, "build_planner_request")
        self.assertEqual(steps[-1].status, "failed")
        self.assertEqual(failed_event.event_type, "skill_run_failed")
        self.assertEqual(failed_event.payload_json["skillRunSummary"]["status"], "failed")
        self.assertEqual(failed_event.payload_json["skillRunSummary"]["errorMessage"], "handler import failed")
        self.assertEqual(run_record.metadata_json["skill"]["status"], "failed")
        self.assertEqual(run_record.metadata_json["skill"]["errorMessage"], "handler import failed")

    def test_step_service_records_failed_step_error(self):
        session = AgentSessionRepository(self.db).create(status="idle", current_step="", progress=0)
        service = AgentStepService(self.db)
        step = service.start_step(
            session_id=session.id,
            step_key="render_video",
            title="渲染视频",
            description="调用渲染流程，生成视频产物或失败原因。",
            sequence=8,
            actor_role="executor",
        )

        failed = service.fail_step(
            step.id,
            message="render failed",
            retryable=True,
            retryable_step="render_video",
        )
        api_step = service.to_api_step(failed)

        self.assertEqual(api_step.status, "failed")
        self.assertEqual(api_step.error.message, "render failed")
        self.assertTrue(api_step.error.retryable)
        self.assertEqual(api_step.error.retryableStep, "render_video")

    def test_trace_recorder_can_persist_trace_event(self):
        session = AgentSessionRepository(self.db).create(status="idle", current_step="", progress=0)
        recorder = TraceRecorder(self.db)

        recorder.record(
            TraceEvent(
                session_id=session.id,
                event_type="planner_decision",
                payload={"message": "selected fallback planner"},
            )
        )

        events = AgentTraceEventRepository(self.db).list_for_session(session.id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "planner_decision")
        self.assertEqual(events[0].message, "selected fallback planner")

    def test_add_user_message_creates_run_and_authoritative_planning_steps(self):
        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session("做一个 30 秒产品介绍视频")

        updated = session_service.add_user_message(session.id, "把节奏改得更快一些")

        runs = AgentRunRepository(self.db).list_for_session(session.id)
        steps = AgentStepRepository(self.db).list_for_run(runs[-1].id)

        self.assertEqual(updated.status.value, "plan_ready")
        self.assertGreaterEqual(len(runs), 1)
        self.assertEqual(runs[-1].status, "succeeded")
        self.assertEqual(
            [step.step_key for step in steps],
            [
                "select_strategy",
                "build_planner_request",
                "understand_request",
                "extract_requirements",
                "generate_options",
                "finalize_plan",
            ],
        )
        self.assertTrue(all(step.status == "succeeded" for step in steps))

    def test_confirm_session_sets_job_operation_and_create_task_step(self):
        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session("做一个 30 秒产品介绍视频")

        enqueued: list[str] = []
        execution_service = AgentExecutionService(
            session_factory=self.SessionLocal,
            enqueue_job=enqueued.append,
        )
        confirmed = execution_service.confirm_session(session.id)

        session_record = AgentSessionRepository(self.db).get(session.id)
        steps = AgentStepRepository(self.db).list_for_job(confirmed.activeJobId)

        self.assertEqual(enqueued, [confirmed.activeJobId])
        self.assertEqual(session_record.active_operation_type, "job")
        self.assertEqual(session_record.active_operation_id, confirmed.activeJobId)
        self.assertEqual([step.step_key for step in steps], ["create_task"])
        self.assertEqual(steps[0].status, "succeeded")

    def test_confirm_session_releases_job_operation_when_enqueue_fails(self):
        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session("做一个 30 秒产品介绍视频")

        def fail_enqueue(_job_id: str) -> None:
            raise RuntimeError("broker unavailable")

        execution_service = AgentExecutionService(
            session_factory=self.SessionLocal,
            enqueue_job=fail_enqueue,
        )

        with self.assertRaisesRegex(RuntimeError, "broker unavailable"):
            execution_service.confirm_session(session.id)

        session_record = AgentSessionRepository(self.db).get(session.id)
        self.assertEqual(session_record.active_operation_type, "none")
        self.assertIsNone(session_record.active_operation_id)
        self.assertEqual(session_record.status, "failed")
        self.assertEqual(session_record.error_retryable_step, "queue")

    def test_confirm_grounding_candidates_is_guarded_by_run_operation(self):
        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session()
        session_service.add_user_message(session.id, "给 Notion AI 做一个 30 秒产品亮点视频")
        session_record = AgentSessionRepository(self.db).get(session.id)
        candidate_ids = [
            candidate["id"]
            for candidate in session_record.grounding_summary_json["candidates"][:1]
        ]

        updated = session_service.confirm_grounding_candidates(session.id, candidate_ids)

        session_record = AgentSessionRepository(self.db).get(session.id)
        runs = AgentRunRepository(self.db).list_for_session(session.id)
        self.assertEqual(updated.status.value, "plan_ready")
        self.assertEqual(session_record.active_operation_type, "none")
        self.assertEqual(runs[-1].trigger_type, "grounding_confirm")
        self.assertEqual(runs[-1].status, "succeeded")

    def test_progress_service_updates_execution_steps_and_finishes_job_operation(self):
        from backend.services.agent_progress_service import AgentProgressService

        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session("做一个 30 秒产品介绍视频")
        execution_service = AgentExecutionService(
            session_factory=self.SessionLocal,
            enqueue_job=lambda _job_id: None,
        )
        confirmed = execution_service.confirm_session(session.id)
        progress_service = AgentProgressService(self.db)

        progress_service.mark_job_running(session.id, confirmed.activeJobId)
        progress_service.mark_clips_ready(session.id, confirmed.activeJobId, 3)
        progress_service.mark_render_started(session.id, confirmed.activeJobId)
        progress_service.mark_job_succeeded(session.id, confirmed.activeJobId, "/output/demo.mp4")

        session_record = AgentSessionRepository(self.db).get(session.id)
        steps = AgentStepRepository(self.db).list_for_job(confirmed.activeJobId)
        status_by_key = {step.step_key: step.status for step in steps}

        self.assertEqual(session_record.active_operation_type, "none")
        self.assertIsNone(session_record.active_operation_id)
        self.assertEqual(status_by_key["create_task"], "succeeded")
        self.assertEqual(status_by_key["search_assets"], "succeeded")
        self.assertEqual(status_by_key["prepare_assets"], "succeeded")
        self.assertEqual(status_by_key["render_video"], "succeeded")

    def test_progress_service_requeues_replacement_job_as_active_operation(self):
        from backend.services.agent_progress_service import AgentProgressService

        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session("做一个 30 秒产品介绍视频")
        execution_service = AgentExecutionService(
            session_factory=self.SessionLocal,
            enqueue_job=lambda _job_id: None,
        )
        confirmed = execution_service.confirm_session(session.id)
        replacement_job = AgentJobRepository(self.db).create(
            session_id=session.id,
            job_type="generate_video",
            status="queued",
        )
        progress_service = AgentProgressService(self.db)

        progress_service.mark_job_failed(session.id, confirmed.activeJobId, "素材搜索失败", "searching")
        progress_service.mark_job_requeued_after_replan(session.id, confirmed.activeJobId, replacement_job.id)

        session_record = AgentSessionRepository(self.db).get(session.id)
        self.assertEqual(session_record.active_operation_type, "job")
        self.assertEqual(session_record.active_operation_id, replacement_job.id)
        self.assertEqual(session_record.active_job_id, replacement_job.id)

    def test_progress_service_fails_execution_step_and_clears_job_operation(self):
        from backend.services.agent_progress_service import AgentProgressService

        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session("做一个 30 秒产品介绍视频")
        execution_service = AgentExecutionService(
            session_factory=self.SessionLocal,
            enqueue_job=lambda _job_id: None,
        )
        confirmed = execution_service.confirm_session(session.id)
        progress_service = AgentProgressService(self.db)

        progress_service.mark_job_running(session.id, confirmed.activeJobId)
        progress_service.mark_job_failed(
            session.id,
            confirmed.activeJobId,
            "素材搜索失败",
            "searching",
        )

        session_record = AgentSessionRepository(self.db).get(session.id)
        failed_step = AgentStepRepository(self.db).get_for_job_step(
            confirmed.activeJobId,
            "search_assets",
        )

        self.assertEqual(session_record.active_operation_type, "none")
        self.assertEqual(failed_step.status, "failed")
        self.assertEqual(failed_step.error_json["message"], "素材搜索失败")
        self.assertEqual(failed_step.error_json["retryableStep"], "search_assets")

    def test_read_session_prefers_persisted_steps(self):
        session_service = AgentSessionService(session_factory=self.SessionLocal)
        session = session_service.create_session("做一个 30 秒产品介绍视频")
        updated = session_service.add_user_message(session.id, "把节奏改得更快一些")

        persisted_steps = AgentStepRepository(self.db).list_for_run(
            AgentRunRepository(self.db).list_for_session(session.id)[-1].id
        )

        self.assertGreater(len(persisted_steps), 0)
        self.assertEqual(updated.steps[0].id, "understand_request")
        self.assertEqual(updated.steps[0].status, "succeeded")
        self.assertEqual(updated.steps[3].id, "finalize_plan")
        self.assertEqual(updated.steps[3].status, "succeeded")

    def test_read_session_overlays_latest_persisted_standard_step_per_key(self):
        session = AgentSessionRepository(self.db).create(status="plan_ready", current_step="", progress=0)
        step_repo = AgentStepRepository(self.db)

        step_repo.create(
            id="step-z",
            session_id=session.id,
            step_key="finalize_plan",
            title="旧计划步骤",
            description="旧步骤描述",
            status="failed",
            progress=0.2,
            summary="旧步骤失败",
            error_json={
                "message": "旧步骤失败",
                "retryable": True,
                "retryableStep": "finalize_plan",
            },
            sequence=4,
            created_at=datetime(2026, 1, 1, 10, 0, 0),
            updated_at=datetime(2026, 1, 1, 10, 0, 0),
        )
        step_repo.create(
            id="step-a",
            session_id=session.id,
            step_key="finalize_plan",
            title="新计划步骤",
            description="新步骤描述",
            status="succeeded",
            progress=1.0,
            summary="新步骤成功",
            result_json={"planId": "new-plan"},
            sequence=4,
            created_at=datetime(2026, 1, 1, 10, 1, 0),
            updated_at=datetime(2026, 1, 1, 10, 1, 0),
        )
        self.db.commit()

        session_response = AgentReadService(self.SessionLocal).read_session(session.id)
        finalize_step = session_response.steps[3]

        self.assertEqual(len(session_response.steps), 8)
        self.assertEqual(finalize_step.id, "finalize_plan")
        self.assertEqual(finalize_step.title, "生成最终执行方案")
        self.assertEqual(finalize_step.description, "根据用户选择生成最终方案、镜头拆分和可确认计划。")
        self.assertEqual(finalize_step.status, "succeeded")
        self.assertEqual(finalize_step.progress, 1.0)
        self.assertEqual(finalize_step.summary, "新步骤成功")
        self.assertEqual(finalize_step.result, {"planId": "new-plan"})
        self.assertIsNone(finalize_step.error)

    def test_step_projection_service_hides_internal_steps_and_keeps_standard_shape(self):
        from backend.app.agent.step_projection_service import StepProjectionService

        session = AgentSessionRepository(self.db).create(status="plan_ready", current_step="", progress=0)
        step_repo = AgentStepRepository(self.db)
        step_repo.create(
            session_id=session.id,
            step_key="rag_retrieval",
            title="内部 RAG 检索",
            description="内部观测步骤",
            status="succeeded",
            progress=1.0,
            summary="命中 2 条上下文",
            sequence=2,
        )
        step_repo.create(
            session_id=session.id,
            step_key="finalize_plan",
            title="内部计划标题",
            description="内部计划描述",
            status="running",
            progress=0.5,
            summary="正在生成计划",
            sequence=4,
        )
        self.db.commit()

        projected_steps = StepProjectionService().build_session_steps(
            session_record=session,
            message_rows=[],
            plan_row=None,
            event_rows=[],
            persisted_step_rows=step_repo.list_for_session(session.id),
        )

        self.assertEqual(len(projected_steps), 8)
        self.assertNotIn("rag_retrieval", [step.id for step in projected_steps])
        self.assertEqual(projected_steps[3].id, "finalize_plan")
        self.assertEqual(projected_steps[3].title, "生成最终执行方案")
        self.assertEqual(projected_steps[3].description, "根据用户选择生成最终方案、镜头拆分和可确认计划。")
        self.assertEqual(projected_steps[3].status, "running")
        self.assertEqual(projected_steps[3].summary, "正在生成计划")

    def test_run_and_trace_rows_map_to_api_models(self):
        session = AgentSessionRepository(self.db).create(status="idle", current_step="", progress=0)
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="user_message",
            status="succeeded",
            summary="已生成方案",
        )
        event = AgentTraceEventRepository(self.db).create(
            session_id=session.id,
            run_id=run.id,
            event_type="run_succeeded",
            message="已生成方案",
            sequence=1,
            actor_role="planner",
        )

        run_summary = AgentRunSummary(
            id=run.id,
            sessionId=run.session_id,
            triggerType=run.trigger_type,
            status=run.status,
            summary=run.summary or "",
            startedAt=run.started_at.isoformat() if run.started_at else None,
            finishedAt=run.finished_at.isoformat() if run.finished_at else None,
            createdAt=run.created_at.isoformat(),
        )
        trace_event = AgentTraceEventModel(
            id=event.id,
            sessionId=event.session_id,
            runId=event.run_id,
            stepId=event.step_id,
            jobId=event.job_id,
            eventType=event.event_type,
            level=event.level,
            message=event.message,
            payload=event.payload_json,
            sequence=event.sequence,
            actorRole=event.actor_role,
            createdAt=event.created_at.isoformat(),
        )

        self.assertEqual(run_summary.triggerType, "user_message")
        self.assertEqual(run_summary.status, "succeeded")
        self.assertEqual(trace_event.eventType, "run_succeeded")
        self.assertEqual(trace_event.actorRole, "planner")


if __name__ == "__main__":
    unittest.main()
