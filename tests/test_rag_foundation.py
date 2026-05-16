from __future__ import annotations

import sqlite3
import unittest
from datetime import datetime

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
        from backend.db.repositories import AgentSessionRepository, KnowledgeRepository
        from backend.domain.knowledge.contracts import RetrievalQuery

        session = AgentSessionRepository(self.db).create(status="active")
        chunk_ids = KnowledgeIngestionService(self.db).ingest_text(
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

    def test_context_engine_records_context_usage_when_db_is_available(self) -> None:
        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.db.repositories import AgentRunRepository, AgentSessionRepository, KnowledgeRepository
        from backend.runtime.context_engine import ContextEngine, ContextRequest
        from backend.runtime.trace_recorder import TraceRecorder

        session = AgentSessionRepository(self.db).create(status="active")
        run = AgentRunRepository(self.db).create(
            session_id=session.id,
            trigger_type="user_message",
        )
        KnowledgeIngestionService(self.db).ingest_text(
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
