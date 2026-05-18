from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base


class RagFoundationDomainTests(unittest.TestCase):
    def test_knowledge_chunk_contract_is_stable(self) -> None:
        from backend.domain.knowledge.contracts import KnowledgeChunk

        chunk = KnowledgeChunk(
            id="chunk-1",
            document_id="doc-1",
            content="开头 3 秒需要明确产品和使用场景。",
            metadata={"topic": "shortform"},
        )

        self.assertEqual(chunk.id, "chunk-1")
        self.assertEqual(chunk.document_id, "doc-1")
        self.assertIn("产品", chunk.content)
        self.assertEqual(chunk.metadata["topic"], "shortform")

    def test_retrieval_result_orders_by_score_contract(self) -> None:
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalResult

        chunk = KnowledgeChunk(
            id="chunk-1",
            document_id="doc-1",
            content="素材关键词应具体到对象、动作和画面风格。",
        )
        result = RetrievalResult(chunk=chunk, score=0.75, matched_terms=["素材", "关键词"])

        self.assertEqual(result.chunk.id, "chunk-1")
        self.assertEqual(result.score, 0.75)
        self.assertEqual(result.matched_terms, ["素材", "关键词"])


class RagFoundationDbTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.close()
        with self.engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()


class RagFoundationPersistenceTests(RagFoundationDbTestCase):
    def test_repositories_create_document_chunk_and_context_usage(self) -> None:
        from backend.db.repositories import AgentSessionRepository, KnowledgeRepository

        session = AgentSessionRepository(self.db).create(status="active")
        repo = KnowledgeRepository(self.db)
        source = repo.create_source(source_type="seed", title="ClipForge seed")
        document = repo.create_document(
            source_id=source.id,
            title="短视频结构原则",
            content="开头 3 秒需要明确产品和使用场景。",
        )
        chunk = repo.create_chunk(
            document_id=document.id,
            chunk_index=0,
            content=document.content,
            token_count=18,
        )
        usage = repo.create_context_usage(
            session_id=session.id,
            query_text="产品介绍视频",
            chunk_id=chunk.id,
            score=0.8,
            usage_type="planning_context",
        )

        self.assertEqual(repo.list_chunks()[0].id, chunk.id)
        self.assertEqual(repo.list_context_usages(session.id)[0].id, usage.id)


class RagFoundationRetrievalTests(RagFoundationDbTestCase):
    def test_lightweight_index_scores_keyword_overlap_and_orders_results(self) -> None:
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery
        from backend.infrastructure.vector.lightweight_index import LightweightVectorIndex

        chunks = [
            KnowledgeChunk(id="chunk-1", document_id="doc-1", content="开头 3 秒需要明确产品和使用场景。"),
            KnowledgeChunk(id="chunk-2", document_id="doc-1", content="素材关键词应具体到对象、动作和画面风格。"),
        ]
        results = LightweightVectorIndex().search(
            RetrievalQuery(text="产品 使用场景", top_k=2),
            chunks,
        )

        self.assertEqual([result.chunk.id for result in results], ["chunk-1"])
        self.assertGreater(results[0].score, 0)
        self.assertEqual(results[0].matched_terms, ["产品", "使用场景"])

    def test_keyword_vector_store_matches_existing_lightweight_index_behavior(self) -> None:
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery
        from backend.infrastructure.vector.store import KeywordVectorStore

        chunks = [
            KnowledgeChunk(id="chunk-1", document_id="doc-1", content="开头 3 秒需要明确产品和使用场景。"),
            KnowledgeChunk(id="chunk-2", document_id="doc-1", content="素材关键词应具体到对象、动作和画面风格。"),
        ]
        results = KeywordVectorStore().search(
            RetrievalQuery(text="产品 使用场景", top_k=2),
            chunks,
        )

        self.assertEqual([result.chunk.id for result in results], ["chunk-1"])
        self.assertEqual(results[0].matched_terms, ["产品", "使用场景"])

    def test_retrieval_service_uses_vector_store_boundary(self) -> None:
        from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
        from backend.domain.knowledge.contracts import RetrievalQuery

        class RecordingVectorStore:
            def __init__(self) -> None:
                self.calls = []

            def search(self, query, chunks):
                self.calls.append((query, chunks))
                return []

        vector_store = RecordingVectorStore()
        results = KnowledgeRetrievalService(index=vector_store).retrieve(
            RetrievalQuery(text="产品", top_k=1)
        )

        self.assertEqual(results, [])
        self.assertEqual(vector_store.calls[0][0].text, "产品")
        self.assertTrue(vector_store.calls[0][1])

    def test_retrieval_pipeline_calls_vector_store_then_reranker(self) -> None:
        from backend.app.knowledge.retrieval_pipeline import RetrievalPipeline
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult

        events = []
        chunk_a = KnowledgeChunk(id="chunk-a", document_id="doc-1", content="产品 使用场景")
        chunk_b = KnowledgeChunk(id="chunk-b", document_id="doc-1", content="产品")

        class RecordingVectorStore:
            def search(self, query, chunks):
                events.append(("search", query.text, [chunk.id for chunk in chunks]))
                return [
                    RetrievalResult(chunk=chunk_a, score=0.5, matched_terms=["产品"]),
                    RetrievalResult(chunk=chunk_b, score=0.9, matched_terms=["产品"]),
                ]

        class RecordingReranker:
            def rerank(self, query, results):
                events.append(("rerank", query.text, [result.chunk.id for result in results]))
                return list(reversed(results))

        results = RetrievalPipeline(
            vector_store=RecordingVectorStore(),
            reranker=RecordingReranker(),
        ).retrieve(RetrievalQuery(text="产品", top_k=1), [chunk_a, chunk_b])

        self.assertEqual([result.chunk.id for result in results], ["chunk-b"])
        self.assertEqual(
            events,
            [
                ("search", "产品", ["chunk-a", "chunk-b"]),
                ("rerank", "产品", ["chunk-a", "chunk-b"]),
            ],
        )

    def test_retrieval_pipeline_records_diagnostics_for_last_run(self) -> None:
        from backend.app.knowledge.retrieval_pipeline import RetrievalPipeline
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult

        chunk_a = KnowledgeChunk(id="chunk-a", document_id="doc-1", content="产品 使用场景")
        chunk_b = KnowledgeChunk(id="chunk-b", document_id="doc-1", content="产品")

        class RecordingVectorStore:
            def search(self, query, chunks):
                return [
                    RetrievalResult(chunk=chunk_a, score=0.4, matched_terms=["产品"]),
                    RetrievalResult(chunk=chunk_b, score=0.9, matched_terms=["产品"]),
                ]

        class ScoreReranker:
            def rerank(self, query, results):
                return sorted(results, key=lambda result: result.score, reverse=True)

        pipeline_result = RetrievalPipeline(
            vector_store=RecordingVectorStore(),
            reranker=ScoreReranker(),
        ).retrieve_with_diagnostics(RetrievalQuery(text="产品", top_k=1), [chunk_a, chunk_b])
        results = pipeline_result.results
        diagnostics = pipeline_result.diagnostics

        self.assertEqual([result.chunk.id for result in results], ["chunk-b"])
        self.assertEqual(diagnostics.query_text, "产品")
        self.assertEqual(diagnostics.input_chunk_count, 2)
        self.assertEqual(diagnostics.candidate_count, 2)
        self.assertEqual(diagnostics.returned_count, 1)
        self.assertEqual(diagnostics.candidate_chunk_ids, ("chunk-a", "chunk-b"))
        self.assertEqual(diagnostics.reranked_chunk_ids, ("chunk-b", "chunk-a"))
        self.assertEqual(diagnostics.returned_chunk_ids, ("chunk-b",))
        self.assertEqual(diagnostics.top_score, 0.9)

    def test_retrieval_pipeline_records_top_score_as_max_returned_score(self) -> None:
        from backend.app.knowledge.retrieval_pipeline import RetrievalPipeline
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult

        chunk_a = KnowledgeChunk(id="chunk-a", document_id="doc-1", content="产品")
        chunk_b = KnowledgeChunk(id="chunk-b", document_id="doc-1", content="使用场景")

        class RecordingVectorStore:
            def search(self, query, chunks):
                return [
                    RetrievalResult(chunk=chunk_a, score=0.4, matched_terms=["产品"]),
                    RetrievalResult(chunk=chunk_b, score=0.9, matched_terms=["使用场景"]),
                ]

        class LowScoreFirstReranker:
            def rerank(self, query, results):
                return results

        pipeline_result = RetrievalPipeline(
            vector_store=RecordingVectorStore(),
            reranker=LowScoreFirstReranker(),
        ).retrieve_with_diagnostics(RetrievalQuery(text="产品 使用场景", top_k=2), [chunk_a, chunk_b])

        self.assertEqual([result.chunk.id for result in pipeline_result.results], ["chunk-a", "chunk-b"])
        self.assertEqual(pipeline_result.diagnostics.top_score, 0.9)

    def test_retrieval_pipeline_records_empty_diagnostics_for_invalid_top_k(self) -> None:
        from backend.app.knowledge.retrieval_pipeline import RetrievalPipeline
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery

        chunk = KnowledgeChunk(id="chunk-a", document_id="doc-1", content="产品")
        pipeline_result = RetrievalPipeline().retrieve_with_diagnostics(
            RetrievalQuery(text="产品", top_k=0),
            [chunk],
        )

        self.assertEqual(pipeline_result.results, [])
        self.assertEqual(pipeline_result.diagnostics.query_text, "产品")
        self.assertEqual(pipeline_result.diagnostics.input_chunk_count, 1)
        self.assertEqual(pipeline_result.diagnostics.candidate_count, 0)
        self.assertEqual(pipeline_result.diagnostics.returned_count, 0)

    def test_retrieval_service_uses_retrieval_pipeline_boundary(self) -> None:
        from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
        from backend.domain.knowledge.contracts import RetrievalQuery

        class RecordingPipeline:
            def __init__(self) -> None:
                self.calls = []

            def retrieve(self, query, chunks):
                self.calls.append((query, chunks))
                return []

        pipeline = RecordingPipeline()
        results = KnowledgeRetrievalService(pipeline=pipeline).retrieve(
            RetrievalQuery(text="素材", top_k=2)
        )

        self.assertEqual(results, [])
        self.assertEqual(pipeline.calls[0][0].text, "素材")
        self.assertTrue(pipeline.calls[0][1])

    def test_retrieval_service_can_return_pipeline_diagnostics(self) -> None:
        from backend.app.knowledge.retrieval_pipeline import RetrievalDiagnostics, RetrievalPipelineResult
        from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalQuery, RetrievalResult

        chunk = KnowledgeChunk(id="chunk-1", document_id="doc-1", content="产品")

        class RecordingPipeline:
            def retrieve_with_diagnostics(self, query, chunks):
                return RetrievalPipelineResult(
                    results=[RetrievalResult(chunk=chunk, score=0.8, matched_terms=["产品"])],
                    diagnostics=RetrievalDiagnostics(
                        query_text=query.text,
                        input_chunk_count=len(chunks),
                        candidate_count=1,
                        returned_count=1,
                        candidate_chunk_ids=("chunk-1",),
                        reranked_chunk_ids=("chunk-1",),
                        returned_chunk_ids=("chunk-1",),
                        top_score=0.8,
                    ),
                )

        result = KnowledgeRetrievalService(pipeline=RecordingPipeline()).retrieve_with_diagnostics(
            RetrievalQuery(text="产品", top_k=1)
        )

        self.assertEqual([item.chunk.id for item in result.results], ["chunk-1"])
        self.assertEqual(result.diagnostics.query_text, "产品")
        self.assertGreaterEqual(result.diagnostics.input_chunk_count, 1)

    def test_retrieval_service_pipeline_takes_precedence_over_index(self) -> None:
        from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
        from backend.domain.knowledge.contracts import RetrievalQuery

        class UnusedVectorStore:
            def search(self, query, chunks):
                raise AssertionError("index should not be used when pipeline is provided")

        class RecordingPipeline:
            def __init__(self) -> None:
                self.called = False

            def retrieve(self, query, chunks):
                self.called = True
                return []

        pipeline = RecordingPipeline()
        results = KnowledgeRetrievalService(
            index=UnusedVectorStore(),
            pipeline=pipeline,
        ).retrieve(RetrievalQuery(text="产品", top_k=1))

        self.assertEqual(results, [])
        self.assertTrue(pipeline.called)

    def test_retrieval_service_only_reads_ready_active_source_chunks(self) -> None:
        from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
        from backend.db.repositories import KnowledgeRepository
        from backend.domain.knowledge.contracts import RetrievalQuery

        repo = KnowledgeRepository(self.db)
        source = repo.create_source(
            project_key="default",
            name="brand.md",
            content_type="text/markdown",
            status="ready",
        )
        version = repo.create_version(
            source_id=source.id,
            version_number=1,
            status="ready",
            content_hash="hash-ready",
            storage_path="default/source/v1/brand.md",
            original_filename="brand.md",
            file_size=100,
            parser_type="markdown",
        )
        repo.activate_version(version.id)
        repo.create_chunk(
            source_id=source.id,
            version_id=version.id,
            chunk_index=0,
            chunk_type="paragraph",
            title_path="",
            content="ClipForge 负责视频生成。",
            token_count=4,
        )

        other = repo.create_source(
            project_key="default",
            name="draft.md",
            content_type="text/markdown",
            status="processing",
        )
        other_version = repo.create_version(
            source_id=other.id,
            version_number=1,
            status="processing",
            content_hash="hash-draft",
            storage_path="default/source/v1/draft.md",
            original_filename="draft.md",
            file_size=10,
            parser_type="markdown",
        )
        repo.set_processing_version(other.id, other_version.id, status="processing")
        repo.create_chunk(
            source_id=other.id,
            version_id=other_version.id,
            chunk_index=0,
            chunk_type="paragraph",
            title_path="",
            content="this chunk should be ignored",
            token_count=5,
        )

        results = KnowledgeRetrievalService(self.db).retrieve(RetrievalQuery(text="视频生成", top_k=3))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk.content, "ClipForge 负责视频生成。")

    def test_retrieval_service_returns_seed_context_chunks(self) -> None:
        from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
        from backend.domain.knowledge.contracts import RetrievalQuery

        service = KnowledgeRetrievalService()
        results = service.retrieve(RetrievalQuery(text="短视频 产品 开头", top_k=3))

        self.assertTrue(results)
        self.assertIn("产品", results[0].chunk.content)

    def test_ingested_text_is_retrievable_and_context_usage_is_recorded(self) -> None:
        from backend.app.knowledge.context_usage_service import ContextUsageService
        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.retrieval_service import KnowledgeRetrievalService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import AgentSessionRepository, KnowledgeRepository
        from backend.domain.knowledge.contracts import RetrievalQuery

        session = AgentSessionRepository(self.db).create(status="active")
        with tempfile.TemporaryDirectory() as tmpdir:
            chunk_ids = KnowledgeIngestionService(
                self.db,
                storage=LocalKnowledgeStorage(Path(tmpdir)),
            ).ingest_text(
                source_type="seed",
                title="产品开头原则",
                content="产品介绍短视频开头需要快速说明使用场景和核心卖点。",
            )

        results = KnowledgeRetrievalService(self.db).retrieve(
            RetrievalQuery(text="产品 使用场景", top_k=3)
        )
        usages = ContextUsageService(self.db).record_results(
            session_id=session.id,
            query_text="产品 使用场景",
            results=results,
        )

        self.assertEqual([result.chunk.id for result in results], chunk_ids)
        self.assertEqual(usages[0].chunk_id, chunk_ids[0])
        self.assertEqual(
            KnowledgeRepository(self.db).list_context_usages(session.id)[0].metadata_json["matchedTerms"],
            ["产品", "使用场景"],
        )


class _FakeTraceRecorder:
    def __init__(self) -> None:
        self.events = []

    def record(self, event) -> None:
        self.events.append(event)


class RagFoundationContextEngineTests(RagFoundationDbTestCase):
    def test_user_revision_context_payload_includes_planner_context_when_documents_match(self) -> None:
        from backend.app.planning.orchestrator import _build_user_revision_context_payload
        from backend.runtime.context_engine import ContextBundle

        payload = _build_user_revision_context_payload(
            "把开头改得更强调产品场景",
            ContextBundle(
                documents=[
                    {
                        "content": "开头 3 秒需要明确产品和使用场景。",
                        "score": 0.9,
                    }
                ]
            ),
        )

        self.assertIn("plannerContext", payload)
        self.assertIn("开头 3 秒需要明确产品和使用场景", payload["plannerContext"])

    def test_user_revision_context_payload_is_empty_without_documents(self) -> None:
        from backend.app.planning.orchestrator import _build_user_revision_context_payload
        from backend.runtime.context_engine import ContextBundle

        payload = _build_user_revision_context_payload(
            "把开头改得更强调产品场景",
            ContextBundle(),
        )

        self.assertEqual(payload, {})

    def test_user_revision_replan_builds_context_with_scope_and_run_id(self) -> None:
        from backend.app.planning import orchestrator as orchestrator_module
        from backend.app.planning.orchestrator import PlannerOrchestrator
        from backend.db.repositories import (
            AgentMessageRepository,
            AgentPlanRepository,
            AgentRunRepository,
            AgentSessionRepository,
        )
        from backend.runtime.context_engine import ContextBundle

        class RecordingContextEngine:
            def __init__(self) -> None:
                self.requests = []

            def build_context(self, request):
                self.requests.append(request)
                return ContextBundle(documents=[{"content": "用户修改时优先保留产品使用场景。"}])

        captured_revision_feedback = {}

        def fake_run_user_revision_replan(**kwargs):
            captured_revision_feedback.update(kwargs["revision_feedback"])
            return {
                "status": "ready",
                "triggerType": "user_revision",
                "changeSummary": "updated",
                "executionPlan": {
                    "title": "Updated plan",
                    "targetDuration": 30,
                    "style": "clean",
                },
                "agentPlan": {"replanHistory": []},
            }

        session = AgentSessionRepository(self.db).create(status="active")
        message = AgentMessageRepository(self.db).create(
            session_id=session.id,
            role="user",
            content="把第 1 个场景改得更贴近使用场景",
        )
        latest_plan = AgentPlanRepository(self.db).create(
            session_id=session.id,
            version=1,
            parent_plan_id=None,
            trigger_type="initial_brief",
            planner_mode="deterministic",
            planner_model="test-model",
            title="Initial plan",
            target_duration=30,
            style="clean",
            plan_json={"scenes": []},
            execution_plan_json={"title": "Initial plan", "targetDuration": 30, "style": "clean"},
            change_summary="initial",
            status="ready",
        )
        session.current_plan_id = latest_plan.id
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="planning",
            status="running",
        )
        self.db.flush()
        context_engine = RecordingContextEngine()
        orchestrator = PlannerOrchestrator(context_engine=context_engine)

        with patch.object(
            orchestrator_module,
            "run_user_revision_replan",
            side_effect=fake_run_user_revision_replan,
        ):
            orchestrator.persist_user_revision_replan(
                self.db,
                session,
                message,
                scene_keyword_updates={1: ["使用场景"]},
                run_id=run.id,
            )

        self.assertEqual(context_engine.requests[0].scope, "user_revision")
        self.assertEqual(context_engine.requests[0].run_id, run.id)
        self.assertIn("plannerContext", captured_revision_feedback)
        self.assertIn("用户修改时优先保留产品使用场景", captured_revision_feedback["plannerContext"])
        refreshed_run = AgentRunRepository(self.db).get(run.id)
        self.assertIn("plannerContext", refreshed_run.input_json["skillSelectionRequest"]["context"])
        self.assertEqual(
            refreshed_run.input_json["skillSelectionRequest"]["context"]["sceneKeywordUpdates"],
            {"1": ["使用场景"]},
        )

    def test_context_engine_returns_documents_and_records_trace(self) -> None:
        from backend.runtime.context_engine import ContextEngine, ContextRequest

        recorder = _FakeTraceRecorder()
        engine = ContextEngine(trace_recorder=recorder)
        bundle = engine.build_context(
            ContextRequest(
                session_id="session-1",
                message="短视频 产品 开头",
                scope="planning",
            )
        )

        self.assertTrue(bundle.documents)
        self.assertTrue(bundle.citations)
        self.assertEqual(recorder.events[0].event_type, "rag_retrieval_started")
        self.assertEqual(recorder.events[-1].event_type, "rag_retrieval_succeeded")
        self.assertEqual(recorder.events[-1].actor_role, "context")

    def test_context_engine_records_stream_shape_for_rag_trace_events(self) -> None:
        from backend.runtime.context_engine import ContextEngine, ContextRequest

        recorder = _FakeTraceRecorder()
        engine = ContextEngine(trace_recorder=recorder)
        engine.build_context(ContextRequest(session_id="session-1", message="短视频 产品 开头"))

        started = recorder.events[0].payload["stream"]
        succeeded = recorder.events[-1].payload["stream"]

        self.assertEqual(started["phase"], "context_retrieval")
        self.assertEqual(started["status"], "running")
        self.assertEqual(started["progress"], 0.1)
        self.assertEqual(started["label"], "检索上下文")
        self.assertEqual(started["message"], "正在检索可用知识。")
        self.assertEqual(succeeded["phase"], "context_retrieval")
        self.assertEqual(succeeded["status"], "succeeded")
        self.assertEqual(succeeded["progress"], 1.0)
        self.assertEqual(succeeded["label"], "上下文检索完成")
        self.assertIn("命中", succeeded["message"])

    def test_context_engine_records_retrieval_diagnostics_in_success_trace(self) -> None:
        from backend.app.knowledge.retrieval_pipeline import RetrievalDiagnostics, RetrievalPipelineResult
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalResult
        from backend.runtime.context_engine import ContextEngine, ContextRequest

        class RetrievalWithDiagnostics:
            def retrieve_with_diagnostics(self, query):
                chunk = KnowledgeChunk(id="chunk-1", document_id="doc-1", content="产品 使用场景")
                return RetrievalPipelineResult(
                    results=[RetrievalResult(chunk=chunk, score=0.75, matched_terms=["产品"])],
                    diagnostics=RetrievalDiagnostics(
                        query_text=query.text,
                        input_chunk_count=2,
                        candidate_count=2,
                        returned_count=1,
                        candidate_chunk_ids=("chunk-1", "chunk-2"),
                        reranked_chunk_ids=("chunk-1", "chunk-2"),
                        returned_chunk_ids=("chunk-1",),
                        top_score=0.75,
                    ),
                )

        recorder = _FakeTraceRecorder()
        engine = ContextEngine(
            retrieval_service=RetrievalWithDiagnostics(),
            trace_recorder=recorder,
        )
        engine.build_context(ContextRequest(session_id="session-1", message="产品"))

        success_payload = recorder.events[-1].payload
        self.assertEqual(success_payload["diagnostics"]["candidateCount"], 2)
        self.assertEqual(success_payload["diagnostics"]["returnedChunkIds"], ["chunk-1"])
        self.assertEqual(success_payload["diagnostics"]["topScore"], 0.75)

    def test_context_engine_success_trace_top_score_uses_diagnostics(self) -> None:
        from backend.app.knowledge.retrieval_pipeline import RetrievalDiagnostics, RetrievalPipelineResult
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalResult
        from backend.runtime.context_engine import ContextEngine, ContextRequest

        class RetrievalWithUnsortedScores:
            def retrieve_with_diagnostics(self, query):
                low = KnowledgeChunk(id="chunk-low", document_id="doc-1", content="产品")
                high = KnowledgeChunk(id="chunk-high", document_id="doc-1", content="使用场景")
                return RetrievalPipelineResult(
                    results=[
                        RetrievalResult(chunk=low, score=0.2, matched_terms=["产品"]),
                        RetrievalResult(chunk=high, score=0.9, matched_terms=["使用场景"]),
                    ],
                    diagnostics=RetrievalDiagnostics(
                        query_text=query.text,
                        input_chunk_count=2,
                        candidate_count=2,
                        returned_count=2,
                        returned_chunk_ids=("chunk-low", "chunk-high"),
                        top_score=0.9,
                    ),
                )

        recorder = _FakeTraceRecorder()
        engine = ContextEngine(
            retrieval_service=RetrievalWithUnsortedScores(),
            trace_recorder=recorder,
        )
        engine.build_context(ContextRequest(session_id="session-1", message="产品"))

        self.assertEqual(recorder.events[-1].payload["topScore"], 0.9)

    def test_context_engine_surfaces_chunk_metadata_in_documents_and_citations(self) -> None:
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalResult
        from backend.runtime.context_engine import ContextEngine, ContextRequest

        class RetrievalWithStructuredChunk:
            def retrieve(self, query):
                return [
                    RetrievalResult(
                        chunk=KnowledgeChunk(
                            id="chunk-1",
                            document_id="source-1",
                            content="ClipForge 负责视频生成。",
                            metadata={
                                "source_id": "source-1",
                                "version_id": "version-1",
                                "title_path": "Brand / Tone",
                                "chunk_type": "paragraph",
                            },
                        ),
                        score=0.9,
                        matched_terms=["视频生成"],
                    )
                ]

        engine = ContextEngine(retrieval_service=RetrievalWithStructuredChunk(), trace_recorder=_FakeTraceRecorder())
        bundle = engine.build_context(ContextRequest(session_id="session-1", message="视频生成"))

        self.assertEqual(bundle.documents[0]["sourceId"], "source-1")
        self.assertEqual(bundle.documents[0]["versionId"], "version-1")
        self.assertEqual(bundle.documents[0]["titlePath"], "Brand / Tone")
        self.assertEqual(bundle.documents[0]["chunkType"], "paragraph")
        self.assertEqual(bundle.citations[0]["sourceId"], "source-1")
        self.assertEqual(bundle.citations[0]["versionId"], "version-1")

    def test_context_engine_returns_empty_context_when_retrieval_fails(self) -> None:
        from backend.runtime.context_engine import ContextEngine, ContextRequest

        class FailingRetrievalService:
            def retrieve(self, query):
                raise RuntimeError("retrieval unavailable")

        recorder = _FakeTraceRecorder()
        engine = ContextEngine(retrieval_service=FailingRetrievalService(), trace_recorder=recorder)
        bundle = engine.build_context(ContextRequest(session_id="session-1", message="anything"))

        self.assertEqual(bundle.documents, [])
        self.assertEqual(recorder.events[-1].event_type, "rag_retrieval_failed")
        stream = recorder.events[-1].payload["stream"]
        self.assertEqual(stream["phase"], "context_retrieval")
        self.assertEqual(stream["status"], "failed")
        self.assertEqual(stream["progress"], 1.0)
        self.assertEqual(stream["label"], "上下文检索失败")

    def test_context_engine_records_context_usage_when_db_is_available(self) -> None:
        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import AgentRunRepository, AgentSessionRepository, KnowledgeRepository
        from backend.runtime.context_engine import ContextEngine, ContextRequest
        from backend.runtime.trace_recorder import TraceRecorder

        session = AgentSessionRepository(self.db).create(status="active")
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="user_message",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            KnowledgeIngestionService(
                self.db,
                storage=LocalKnowledgeStorage(Path(tmpdir)),
            ).ingest_text(
                source_type="seed",
                title="产品开头原则",
                content="产品介绍短视频开头需要快速说明使用场景和核心卖点。",
            )
        recorder = TraceRecorder(self.db)
        engine = ContextEngine(db_session=self.db, trace_recorder=recorder)

        bundle = engine.build_context(
            ContextRequest(
                session_id=session.id,
                run_id=run.id,
                message="短视频 产品 开头",
                scope="planning",
            )
        )
        self.db.commit()

        usages = KnowledgeRepository(self.db).list_context_usages(session.id)
        self.assertTrue(bundle.documents)
        self.assertTrue(usages)
        self.assertEqual(usages[0].usage_type, "planning_context")
        self.assertEqual(usages[0].run_id, run.id)

    def test_context_engine_skips_context_usage_for_non_persisted_chunks(self) -> None:
        from backend.db.repositories import AgentSessionRepository, AgentTraceEventRepository
        from backend.domain.knowledge.contracts import KnowledgeChunk, RetrievalResult
        from backend.runtime.context_engine import ContextEngine, ContextRequest
        from backend.runtime.trace_recorder import TraceRecorder

        class RetrievalWithMissingChunk:
            def retrieve(self, query):
                return [
                    RetrievalResult(
                        chunk=KnowledgeChunk(
                            id="missing-chunk",
                            document_id="missing-document",
                            content="产品介绍短视频开头需要说明使用场景。",
                        ),
                        score=0.8,
                        matched_terms=["产品"],
                    )
                ]

        session = AgentSessionRepository(self.db).create(status="active")
        engine = ContextEngine(
            db_session=self.db,
            retrieval_service=RetrievalWithMissingChunk(),
            trace_recorder=TraceRecorder(self.db),
        )

        bundle = engine.build_context(ContextRequest(session_id=session.id, message="产品"))
        self.db.commit()

        events = AgentTraceEventRepository(self.db).list_for_session(session.id)
        self.assertTrue(bundle.documents)
        self.assertNotIn("rag_context_usage_failed", [event.event_type for event in events])
        self.assertEqual(events[-1].event_type, "rag_retrieval_succeeded")
        self.assertEqual(events[-1].payload_json["usageIds"], [])


class RagFoundationPlannerContextTests(unittest.TestCase):
    def test_format_context_for_planner_adds_known_context_block(self) -> None:
        from backend.runtime.context_engine import ContextBundle
        from backend.services.planner_orchestrator import format_context_for_planner

        context = ContextBundle(
            documents=[
                {"content": "短视频开头 3 秒需要明确产品和使用场景。"},
                {"content": "素材关键词应具体到对象、动作和画面风格。"},
            ],
            confidence=0.75,
        )

        formatted = format_context_for_planner("帮我做一个产品介绍视频", context)

        self.assertIn("Known context:", formatted)
        self.assertIn("短视频开头 3 秒", formatted)
        self.assertIn("素材关键词", formatted)
        self.assertNotIn("帮我做一个产品介绍视频", formatted)

    def test_format_context_for_planner_keeps_prompt_when_context_empty(self) -> None:
        from backend.runtime.context_engine import ContextBundle
        from backend.services.planner_orchestrator import format_context_for_planner

        self.assertEqual(
            format_context_for_planner("原始 brief", ContextBundle()),
            "",
        )

    def test_context_text_does_not_change_deterministic_planner_goal(self) -> None:
        from backend.services.planner_graph import run_initial_planning

        state = run_initial_planning(
            "session-1",
            "原始 brief",
            context_text="Known context:\n- 产品 使用场景 素材关键词",
        )

        self.assertEqual(state["agentPlan"]["goal"], "原始 brief")


class RagFoundationMigrationTests(unittest.TestCase):
    def test_rag_foundation_migration_upgrades_and_downgrades_tables(self) -> None:
        import importlib.util
        import sys
        import types
        from pathlib import Path
        from unittest.mock import patch

        from alembic.operations import Operations
        from alembic.runtime.migration import MigrationContext

        engine = create_engine("sqlite:///:memory:")
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "backend"
            / "alembic"
            / "versions"
            / "20260516_add_rag_foundation.py"
        )

        with engine.connect() as connection:
            connection.execute(text("PRAGMA foreign_keys=ON"))
            now = datetime.utcnow()
            connection.execute(
                text(
                    """
                    CREATE TABLE agent_sessions (
                        id VARCHAR(36) PRIMARY KEY,
                        status VARCHAR(32) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE agent_runs (
                        id VARCHAR(36) PRIMARY KEY,
                        session_id VARCHAR(36) NOT NULL,
                        trigger_type VARCHAR(64) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        created_at DATETIME NOT NULL,
                        updated_at DATETIME NOT NULL,
                        FOREIGN KEY(session_id) REFERENCES agent_sessions(id)
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO agent_sessions (id, status, created_at, updated_at)
                    VALUES ('session-1', 'active', :created_at, :updated_at)
                    """
                ),
                {"created_at": now, "updated_at": now},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO agent_runs (id, session_id, trigger_type, status, created_at, updated_at)
                    VALUES ('run-1', 'session-1', 'user_message', 'running', :created_at, :updated_at)
                    """
                ),
                {"created_at": now, "updated_at": now},
            )
            connection.commit()

            migration_context = MigrationContext.configure(connection)
            fake_alembic = types.ModuleType("alembic")
            fake_alembic.op = Operations(migration_context)
            spec = importlib.util.spec_from_file_location(
                "clipforge_rag_foundation_migration",
                migration_path,
            )
            module = importlib.util.module_from_spec(spec)

            with patch.dict(sys.modules, {"alembic": fake_alembic}, clear=False):
                spec.loader.exec_module(module)
                module.upgrade()

            tables = set(inspect(connection).get_table_names())
            self.assertIn("knowledge_sources", tables)
            self.assertIn("knowledge_documents", tables)
            self.assertIn("knowledge_chunks", tables)
            self.assertIn("agent_context_usages", tables)

            connection.execute(
                text(
                    """
                    INSERT INTO knowledge_sources (id, source_type, title, metadata_json, created_at)
                    VALUES ('source-1', 'seed', 'Seed', '{}', :created_at)
                    """
                ),
                {"created_at": now},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO knowledge_documents (id, source_id, title, content, metadata_json, created_at)
                    VALUES ('doc-1', 'source-1', 'Doc', 'content', '{}', :created_at)
                    """
                ),
                {"created_at": now},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO knowledge_chunks (
                        id, document_id, chunk_index, content, token_count, metadata_json, created_at
                    )
                    VALUES ('chunk-1', 'doc-1', 0, 'content', 1, '{}', :created_at)
                    """
                ),
                {"created_at": now},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO agent_context_usages (
                        id, session_id, run_id, source, query_text, chunk_id,
                        score, usage_type, metadata_json, created_at
                    )
                    VALUES (
                        'usage-1', 'session-1', 'run-1', 'knowledge', 'content',
                        'chunk-1', 1.0, 'planning_context', '{}', :created_at
                    )
                    """
                ),
                {"created_at": now},
            )

            module.downgrade()
            downgraded_tables = set(inspect(connection).get_table_names())
            self.assertNotIn("agent_context_usages", downgraded_tables)
            self.assertNotIn("knowledge_chunks", downgraded_tables)
            self.assertNotIn("knowledge_documents", downgraded_tables)
            self.assertNotIn("knowledge_sources", downgraded_tables)

        engine.dispose()
