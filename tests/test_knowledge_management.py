import asyncio
import importlib
import importlib.util
import inspect
from io import BytesIO
import sqlite3
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.db.base import Base


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _make_test_client(app):
    import httpx

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _make_docx_bytes(text: str) -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body><w:p><w:r><w:t>"
        f"{text}"
        "</w:t></w:r></w:p></w:body></w:document>"
    )
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


def _make_pdf_bytes(text: str) -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 44 >> stream\n"
        b"BT /F1 12 Tf 72 720 Td ("
        + text.encode("utf-8")
        + b") Tj ET\n"
        b"endstream endobj\n"
        b"trailer << /Root 1 0 R >>\n%%EOF\n"
    )


class KnowledgeModelsContractTests(unittest.TestCase):
    def test_knowledge_source_summary_contract_fields(self):
        from backend.models.knowledge import KnowledgeSourceSummary

        self.assertEqual(
            set(KnowledgeSourceSummary.model_fields.keys()),
            {
                "id",
                "name",
                "status",
                "contentType",
                "createdAt",
                "updatedAt",
                "errorSummary",
                "activeVersion",
                "processingVersion",
                "lastFailedVersion",
                "deletionRequestedAt",
            },
        )

    def test_knowledge_version_summary_contract_fields(self):
        from backend.models.knowledge import KnowledgeVersionSummary

        self.assertEqual(
            set(KnowledgeVersionSummary.model_fields.keys()),
            {
                "id",
                "versionNumber",
                "contentHash",
                "status",
                "createdAt",
                "updatedAt",
                "failedAt",
                "reason",
            },
        )

    def test_knowledge_chunk_preview_contract_fields(self):
        from backend.models.knowledge import KnowledgeChunkPreview

        self.assertEqual(
            set(KnowledgeChunkPreview.model_fields.keys()),
            {
                "id",
                "versionId",
                "chunkIndex",
                "chunkType",
                "titlePath",
                "contentPreview",
                "tokenCount",
                "metadata",
            },
        )

    def test_knowledge_source_detail_contract_fields(self):
        from backend.models.knowledge import KnowledgeSourceDetail

        self.assertEqual(
            set(KnowledgeSourceDetail.model_fields.keys()),
            {
                "source",
                "activeChunks",
            },
        )


class KnowledgeRouterContractTests(unittest.TestCase):
    @staticmethod
    def _get_route(path: str, method: str):
        from backend.api.knowledge import router

        for route in router.routes:
            if route.path == path and method in route.methods:
                return route
        raise AssertionError(f"Route not found: {method} {path}")

    def test_knowledge_router_declares_expected_paths(self):
        from backend.api.knowledge import router

        paths = {route.path for route in router.routes}

        self.assertIn("/knowledge-sources/upload", paths)
        self.assertIn("/knowledge-sources/{source_id}", paths)
        self.assertIn("/knowledge-sources/{source_id}/detail", paths)
        self.assertIn("/knowledge-sources/{source_id}/versions", paths)
        self.assertIn("/knowledge-sources/{source_id}/retry", paths)
        self.assertIn("/knowledge-sources", paths)

    def test_backend_main_registers_knowledge_router_under_api_prefix(self):
        module = importlib.import_module("backend.main")
        paths = {route.path for route in module.app.routes}

        self.assertIn("/api/knowledge-sources/upload", paths)
        self.assertIn("/api/knowledge-sources/{source_id}", paths)
        self.assertIn("/api/knowledge-sources/{source_id}/detail", paths)
        self.assertIn("/api/knowledge-sources/{source_id}/versions", paths)
        self.assertIn("/api/knowledge-sources/{source_id}/retry", paths)
        self.assertIn("/api/knowledge-sources", paths)

    def test_upload_endpoint_declares_upload_file_shape(self):
        route = self._get_route("/knowledge-sources/upload", "POST")
        parameter = inspect.signature(route.endpoint).parameters["file"]

        self.assertEqual(parameter.annotation, "UploadFile")
        self.assertEqual(parameter.default.media_type, "multipart/form-data")

    def test_upload_route_declares_summary_response_model(self):
        from backend.models.knowledge import KnowledgeSourceSummary

        route = self._get_route("/knowledge-sources/upload", "POST")
        parameter = inspect.signature(route.endpoint).parameters["file"]

        self.assertEqual(parameter.annotation, "UploadFile")
        self.assertIs(route.response_model, KnowledgeSourceSummary)

    def test_knowledge_get_route_declares_summary_response_model(self):
        from backend.models.knowledge import KnowledgeSourceSummary

        route = self._get_route("/knowledge-sources/{source_id}", "GET")

        self.assertIs(route.response_model, KnowledgeSourceSummary)

    def test_knowledge_delete_route_declares_summary_response_model(self):
        from backend.models.knowledge import KnowledgeSourceSummary

        route = self._get_route("/knowledge-sources/{source_id}", "DELETE")

        self.assertIs(route.response_model, KnowledgeSourceSummary)

    def test_knowledge_list_route_declares_list_summary_response_model(self):
        from backend.models.knowledge import KnowledgeSourceSummary

        route = self._get_route("/knowledge-sources", "GET")

        self.assertEqual(route.response_model, list[KnowledgeSourceSummary])

    def test_knowledge_detail_route_declares_detail_response_model(self):
        from backend.models.knowledge import KnowledgeSourceDetail

        route = self._get_route("/knowledge-sources/{source_id}/detail", "GET")

        self.assertIs(route.response_model, KnowledgeSourceDetail)

    def test_knowledge_versions_route_declares_list_version_response_model(self):
        from backend.models.knowledge import KnowledgeVersionSummary

        route = self._get_route("/knowledge-sources/{source_id}/versions", "GET")

        self.assertEqual(route.response_model, list[KnowledgeVersionSummary])

    def test_knowledge_retry_route_declares_summary_response_model(self):
        from backend.models.knowledge import KnowledgeSourceSummary

        route = self._get_route("/knowledge-sources/{source_id}/retry", "POST")

        self.assertIs(route.response_model, KnowledgeSourceSummary)


class KnowledgeManagementPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

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
        self.db.rollback()
        self.db.close()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            Base.metadata.drop_all(bind=connection)
        self.engine.dispose()

    def test_repository_persists_source_version_and_active_chunks_lifecycle(self):
        from backend.db.repositories import KnowledgeRepository

        repo = KnowledgeRepository(self.db)
        source = repo.create_source(
            project_key="project-alpha",
            name="ClipForge Playbook",
            content_type="text/markdown",
            status="pending",
        )
        version1 = repo.create_version(
            source_id=source.id,
            version_number=1,
            status="uploaded",
            content_hash="hash-v1",
            original_filename="playbook-v1.md",
            file_size=128,
            parser_type="markdown",
        )

        repo.set_processing_version(source.id, version1.id)
        repo.update_version_storage_path(version1.id, "knowledge/project-alpha/source-1/v1.md")
        repo.activate_version(version1.id)
        chunk1 = repo.create_chunk(
            source_id=source.id,
            version_id=version1.id,
            chunk_index=0,
            chunk_type="paragraph",
            title_path="Intro",
            content="短视频开头需要先明确使用场景。",
            token_count=14,
            metadata_json={"section": "intro"},
        )

        version2 = repo.create_version(
            source_id=source.id,
            version_number=2,
            status="uploaded",
            content_hash="hash-v2",
            original_filename="playbook-v2.md",
            file_size=256,
            parser_type="markdown",
        )
        repo.set_processing_version(source.id, version2.id)
        repo.mark_version_failed(version2.id, "parser crashed")
        repo.mark_source_deleting(source.id)
        repo.mark_source_deleted(source.id)

        persisted_source = repo.get_source(source.id)
        persisted_version1 = repo.get_version(version1.id)
        persisted_version2 = repo.get_version(version2.id)
        active_chunks = repo.list_active_chunks(source.id)

        self.assertEqual(persisted_source.project_key, "project-alpha")
        self.assertEqual(persisted_source.active_version_id, version1.id)
        self.assertIsNone(persisted_source.processing_version_id)
        self.assertEqual(persisted_source.last_failed_version_id, version2.id)
        self.assertEqual(persisted_source.status, "deleted")
        self.assertIsNotNone(persisted_source.deletion_requested_at)
        self.assertIsNotNone(persisted_source.deleted_at)
        self.assertEqual(persisted_source.error_message, "parser crashed")

        self.assertEqual(persisted_version1.storage_path, "knowledge/project-alpha/source-1/v1.md")
        self.assertEqual(persisted_version1.status, "active")
        self.assertIsNotNone(persisted_version1.activated_at)

        self.assertEqual(persisted_version2.status, "failed")
        self.assertEqual(persisted_version2.error_message, "parser crashed")
        self.assertIsNotNone(persisted_version2.failed_at)

        self.assertEqual(len(active_chunks), 1)
        self.assertEqual(active_chunks[0].id, chunk1.id)
        self.assertEqual(active_chunks[0].version_id, version1.id)
        self.assertEqual(active_chunks[0].metadata_json["section"], "intro")

    def test_repository_lists_sources_by_updated_desc_and_excludes_deleted(self):
        from backend.db.repositories import KnowledgeRepository

        repo = KnowledgeRepository(self.db)
        active_old = repo.create_source(
            id="source-1",
            project_key="default",
            name="Old Active",
            content_type="text/markdown",
            status="ready",
        )
        active_new = repo.create_source(
            id="source-2",
            project_key="default",
            name="New Active",
            content_type="text/markdown",
            status="ready",
        )
        deleted = repo.create_source(
            id="source-deleted",
            project_key="default",
            name="Deleted Source",
            content_type="text/markdown",
            status="deleted",
        )
        repo.mark_source_deleted(deleted.id)

        self.db.flush()
        active_old.updated_at = active_new.updated_at
        self.db.flush()
        self.db.refresh(active_old)
        self.db.refresh(active_new)

        sources = repo.list_sources()

        self.assertEqual([source.id for source in sources], [active_new.id, active_old.id])
        self.assertNotIn(deleted.id, [source.id for source in sources])

    def test_phase2_2_migration_module_exists_with_upgrade_and_downgrade(self):
        migration_path = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260517_add_knowledge_management_phase2_2.py"
        )

        self.assertTrue(migration_path.exists())

        spec = importlib.util.spec_from_file_location("km_phase2_2", migration_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertTrue(callable(module.upgrade))
        self.assertTrue(callable(module.downgrade))
        self.assertEqual(module.revision, "20260517_add_knowledge_management_phase2_2")
        self.assertEqual(module.down_revision, "20260516_add_rag_foundation")

    def test_phase2_2_migration_upgrades_rag_foundation_schema(self):
        rag_foundation_path = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260516_add_rag_foundation.py"
        )
        phase2_2_path = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260517_add_knowledge_management_phase2_2.py"
        )

        with tempfile.NamedTemporaryFile(suffix=".db") as temp_db:
            engine = create_engine(f"sqlite:///{temp_db.name}")
            with engine.begin() as connection:
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

            with engine.connect() as connection:
                migration_context = MigrationContext.configure(connection)
                fake_alembic = types.ModuleType("alembic")
                fake_alembic.op = Operations(migration_context)

                rag_spec = importlib.util.spec_from_file_location("clipforge_rag_foundation_migration", rag_foundation_path)
                rag_module = importlib.util.module_from_spec(rag_spec)
                with patch.dict(sys.modules, {"alembic": fake_alembic}, clear=False):
                    rag_spec.loader.exec_module(rag_module)
                    rag_module.upgrade()

                phase2_spec = importlib.util.spec_from_file_location("clipforge_phase2_2_migration", phase2_2_path)
                phase2_module = importlib.util.module_from_spec(phase2_spec)
                with patch.dict(sys.modules, {"alembic": fake_alembic}, clear=False):
                    phase2_spec.loader.exec_module(phase2_module)
                    phase2_module.upgrade()

                tables = set(sa_inspect(connection).get_table_names())
                self.assertIn("knowledge_sources", tables)
                self.assertIn("knowledge_versions", tables)
                self.assertIn("knowledge_chunks", tables)
                self.assertNotIn("knowledge_documents", tables)

                source_columns = {column["name"] for column in sa_inspect(connection).get_columns("knowledge_sources")}
                self.assertIn("project_key", source_columns)
                self.assertIn("active_version_id", source_columns)
                self.assertNotIn("source_type", source_columns)

                chunk_foreign_keys = sa_inspect(connection).get_foreign_keys("agent_context_usages")
                referred_tables = {fk["referred_table"] for fk in chunk_foreign_keys if fk["constrained_columns"] == ["chunk_id"]}
                self.assertEqual(referred_tables, {"knowledge_chunks"})

            engine.dispose()


class KnowledgeManagementStorageTests(unittest.TestCase):
    def test_local_storage_saves_upload_and_reopens_content(self) -> None:
        from tempfile import TemporaryDirectory

        from backend.app.knowledge.storage import LocalKnowledgeStorage

        with TemporaryDirectory() as temp_dir:
            storage = LocalKnowledgeStorage(Path(temp_dir))
            saved = storage.save_upload(
                project_key="default",
                source_id="source-1",
                version_number=1,
                filename="brand-guidelines.md",
                content=b"# Brand\nClipForge",
            )

            self.assertTrue(storage.exists(saved.storage_path))
            self.assertIn("brand-guidelines.md", saved.storage_path)
            with storage.open(saved.storage_path) as handle:
                self.assertEqual(handle.read().decode("utf-8"), "# Brand\nClipForge")

            storage.delete(saved.storage_path)
            self.assertFalse(storage.exists(saved.storage_path))


class KnowledgeManagementChunkingTests(unittest.TestCase):
    def test_chunk_text_splits_paragraphs_by_blank_lines(self) -> None:
        from backend.app.knowledge.chunking import chunk_text

        chunks = chunk_text("第一段。\n\n第二段。")

        self.assertEqual([chunk.chunk_type for chunk in chunks], ["paragraph", "paragraph"])
        self.assertEqual([chunk.content for chunk in chunks], ["第一段。", "第二段。"])

    def test_markdown_chunker_preserves_heading_paths_list_blocks_and_code_blocks(self) -> None:
        from backend.app.knowledge.chunking import chunk_markdown_text

        chunks = chunk_markdown_text(
            "# 产品定位\nClipForge 是视频 Agent。\n\n## API\n- 创建知识源\n- 查询状态\n\n```ts\nfetch('/api')\n```"
        )

        self.assertEqual(chunks[0].title_path, "产品定位")
        self.assertEqual(chunks[0].chunk_type, "paragraph")
        self.assertTrue(any(chunk.chunk_type == "list_block" and chunk.title_path == "产品定位 / API" for chunk in chunks))
        self.assertTrue(any(chunk.chunk_type == "code_block" and chunk.title_path == "产品定位 / API" for chunk in chunks))


class KnowledgeManagementPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self.db = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            Base.metadata.drop_all(bind=connection)
        self.engine.dispose()

    def test_upload_service_reuses_source_for_same_name_and_content(self) -> None:
        from tempfile import TemporaryDirectory

        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.app.knowledge.upload_service import KnowledgeUploadService
        from backend.db.repositories import KnowledgeRepository

        calls: list[str] = []

        def dispatch(version_id: str) -> None:
            calls.append(version_id)

        with TemporaryDirectory() as temp_dir:
            service = KnowledgeUploadService(
                self.db,
                storage=LocalKnowledgeStorage(Path(temp_dir)),
                dispatch_ingestion=dispatch,
            )

            first = service.upload(
                project_key="project-alpha",
                filename="brand-guidelines.md",
                content=b"# Brand\n\nClipForge",
            )
            second = service.upload(
                project_key="project-alpha",
                filename="brand-guidelines.md",
                content=b"# Brand\n\nClipForge",
            )

            repo = KnowledgeRepository(self.db)

            self.assertEqual(first.id, second.id)
            self.assertEqual(len(repo.list_versions(first.id)), 1)
            self.assertEqual(calls, [first.processingVersion.id])

    def test_ingestion_service_activates_version_and_writes_chunks_for_markdown(self) -> None:
        from tempfile import TemporaryDirectory

        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import KnowledgeRepository

        with TemporaryDirectory() as temp_dir:
            storage = LocalKnowledgeStorage(Path(temp_dir))
            repo = KnowledgeRepository(self.db)
            source = repo.create_source(
                project_key="project-alpha",
                name="brand-guidelines.md",
                content_type="text/markdown",
                status="uploaded",
            )
            version = repo.create_version(
                source_id=source.id,
                version_number=1,
                status="uploaded",
                content_hash="hash-v1",
                original_filename="brand-guidelines.md",
                file_size=18,
                parser_type="markdown",
            )
            saved = storage.save_upload(
                project_key=source.project_key,
                source_id=source.id,
                version_number=version.version_number,
                filename="brand-guidelines.md",
                content=b"# Brand\n\nClipForge",
            )
            repo.set_processing_version(source.id, version.id)
            repo.update_version_storage_path(version.id, saved.storage_path)

            chunk_ids = KnowledgeIngestionService(self.db, storage=storage).ingest_version(version.id)

            persisted_source = repo.get_source(source.id)
            persisted_version = repo.get_version(version.id)
            active_chunks = repo.list_active_chunks(source.id)

            self.assertEqual(persisted_source.status, "ready")
            self.assertEqual(persisted_source.active_version_id, version.id)
            self.assertIsNone(persisted_source.processing_version_id)
            self.assertEqual(persisted_version.status, "active")
            self.assertEqual(chunk_ids, [chunk.id for chunk in active_chunks])
            self.assertTrue(any(chunk.chunk_type == "paragraph" for chunk in active_chunks))

    def test_ingestion_service_extracts_docx_text(self) -> None:
        from tempfile import TemporaryDirectory

        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import KnowledgeRepository

        with TemporaryDirectory() as temp_dir:
            storage = LocalKnowledgeStorage(Path(temp_dir))
            repo = KnowledgeRepository(self.db)
            source = repo.create_source(
                project_key="default",
                name="brief.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                status="pending",
            )
            version = repo.create_version(
                source_id=source.id,
                version_number=1,
                status="uploaded",
                content_hash="hash-docx",
                original_filename="brief.docx",
                file_size=128,
                parser_type="docx",
            )
            saved = storage.save_upload(
                project_key=source.project_key,
                source_id=source.id,
                version_number=version.version_number,
                filename="brief.docx",
                content=_make_docx_bytes("ClipForge docx knowledge"),
            )
            repo.set_processing_version(source.id, version.id)
            repo.update_version_storage_path(version.id, saved.storage_path)

            KnowledgeIngestionService(self.db, storage=storage).ingest_version(version.id)

            active_chunks = repo.list_active_chunks(source.id)
            self.assertEqual([chunk.content for chunk in active_chunks], ["ClipForge docx knowledge"])

    def test_ingestion_service_extracts_simple_pdf_text(self) -> None:
        from tempfile import TemporaryDirectory

        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import KnowledgeRepository

        with TemporaryDirectory() as temp_dir:
            storage = LocalKnowledgeStorage(Path(temp_dir))
            repo = KnowledgeRepository(self.db)
            source = repo.create_source(
                project_key="default",
                name="brief.pdf",
                content_type="application/pdf",
                status="pending",
            )
            version = repo.create_version(
                source_id=source.id,
                version_number=1,
                status="uploaded",
                content_hash="hash-pdf",
                original_filename="brief.pdf",
                file_size=128,
                parser_type="pdf",
            )
            saved = storage.save_upload(
                project_key=source.project_key,
                source_id=source.id,
                version_number=version.version_number,
                filename="brief.pdf",
                content=_make_pdf_bytes("ClipForge PDF knowledge"),
            )
            repo.set_processing_version(source.id, version.id)
            repo.update_version_storage_path(version.id, saved.storage_path)

            KnowledgeIngestionService(self.db, storage=storage).ingest_version(version.id)

            active_chunks = repo.list_active_chunks(source.id)
            self.assertEqual([chunk.content for chunk in active_chunks], ["ClipForge PDF knowledge"])

    def test_ingestion_service_restores_previous_active_version_when_new_version_fails(self) -> None:
        from tempfile import TemporaryDirectory

        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import KnowledgeRepository

        with TemporaryDirectory() as temp_dir:
            storage = LocalKnowledgeStorage(Path(temp_dir))
            repo = KnowledgeRepository(self.db)
            source = repo.create_source(
                project_key="project-alpha",
                name="brand-guidelines.md",
                content_type="text/markdown",
                status="uploaded",
            )
            version1 = repo.create_version(
                source_id=source.id,
                version_number=1,
                status="uploaded",
                content_hash="hash-v1",
                original_filename="brand-guidelines.md",
                file_size=18,
                parser_type="markdown",
            )
            saved_v1 = storage.save_upload(
                project_key=source.project_key,
                source_id=source.id,
                version_number=version1.version_number,
                filename="brand-guidelines.md",
                content=b"# Brand\n\nClipForge",
            )
            repo.set_processing_version(source.id, version1.id)
            repo.update_version_storage_path(version1.id, saved_v1.storage_path)
            KnowledgeIngestionService(self.db, storage=storage).ingest_version(version1.id)

            version2 = repo.create_version(
                source_id=source.id,
                version_number=2,
                status="uploaded",
                content_hash="hash-v2",
                original_filename="brand-guidelines.md",
                file_size=8,
                parser_type="markdown",
            )
            repo.set_processing_version(source.id, version2.id)
            repo.update_version_storage_path(version2.id, "missing/brand-guidelines.md")

            with self.assertRaises(FileNotFoundError):
                KnowledgeIngestionService(self.db, storage=storage).ingest_version(version2.id)

            persisted_source = repo.get_source(source.id)
            persisted_version2 = repo.get_version(version2.id)

            self.assertEqual(persisted_source.status, "ready")
            self.assertEqual(persisted_source.active_version_id, version1.id)
            self.assertIsNone(persisted_source.processing_version_id)
            self.assertEqual(persisted_source.last_failed_version_id, version2.id)
            self.assertEqual(persisted_version2.status, "failed")

    def test_ingestion_service_skips_processing_when_source_is_deleting(self) -> None:
        from tempfile import TemporaryDirectory

        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import KnowledgeRepository

        with TemporaryDirectory() as temp_dir:
            storage = LocalKnowledgeStorage(Path(temp_dir))
            repo = KnowledgeRepository(self.db)
            source = repo.create_source(
                project_key="project-alpha",
                name="brand-guidelines.md",
                content_type="text/markdown",
                status="pending",
            )
            version = repo.create_version(
                source_id=source.id,
                version_number=1,
                status="uploaded",
                content_hash="hash-v1",
                original_filename="brand-guidelines.md",
                file_size=18,
                parser_type="markdown",
            )
            saved = storage.save_upload(
                project_key=source.project_key,
                source_id=source.id,
                version_number=version.version_number,
                filename="brand-guidelines.md",
                content=b"# Brand\n\nClipForge",
            )
            repo.update_version_storage_path(version.id, saved.storage_path)
            repo.mark_source_deleting(source.id)

            chunk_ids = KnowledgeIngestionService(self.db, storage=storage).ingest_version(version.id)

            persisted_source = repo.get_source(source.id)
            active_chunks = repo.list_chunks()

            self.assertEqual(chunk_ids, [])
            self.assertEqual(persisted_source.status, "deleted")
            self.assertFalse(storage.exists(saved.storage_path))
            self.assertEqual(active_chunks, [])

    def test_ingestion_service_stops_when_start_processing_reports_deleted(self) -> None:
        from tempfile import TemporaryDirectory
        from unittest.mock import patch

        from backend.app.knowledge.ingestion_service import KnowledgeIngestionService
        from backend.app.knowledge.storage import LocalKnowledgeStorage
        from backend.db.repositories import KnowledgeRepository

        with TemporaryDirectory() as temp_dir:
            storage = LocalKnowledgeStorage(Path(temp_dir))
            repo = KnowledgeRepository(self.db)
            source = repo.create_source(
                project_key="project-alpha",
                name="brand-guidelines.md",
                content_type="text/markdown",
                status="pending",
            )
            version = repo.create_version(
                source_id=source.id,
                version_number=1,
                status="uploaded",
                content_hash="hash-v1",
                original_filename="brand-guidelines.md",
                file_size=18,
                parser_type="markdown",
            )
            saved = storage.save_upload(
                project_key=source.project_key,
                source_id=source.id,
                version_number=version.version_number,
                filename="brand-guidelines.md",
                content=b"# Brand\n\nClipForge",
            )
            repo.update_version_storage_path(version.id, saved.storage_path)

            service = KnowledgeIngestionService(self.db, storage=storage)

            with patch.object(
                service,
                "start_version_processing",
                return_value={"sourceId": source.id, "sourceStatus": "deleted", "versionId": version.id},
            ), patch.object(storage, "open", side_effect=AssertionError("storage should not be opened")):
                chunk_ids = service.ingest_version(version.id)

            self.assertEqual(chunk_ids, [])

    def test_celery_app_includes_knowledge_task_module(self) -> None:
        from backend.tasks.celery_app import celery_app

        self.assertIn("backend.tasks.knowledge_tasks", celery_app.conf.include)
        self.assertIn("backend.tasks.knowledge_tasks.ingest_knowledge_version", celery_app.tasks)


class KnowledgeManagementConfigTests(unittest.TestCase):
    def test_get_settings_exposes_knowledge_storage_defaults(self) -> None:
        from unittest.mock import patch

        from backend.config import get_settings

        get_settings.cache_clear()
        with patch("backend.config.runtime_config_service.get_effective_value", return_value=None):
            settings = get_settings()

        self.assertEqual(settings.knowledge_storage_dir, "backend/storage/knowledge")
        self.assertEqual(settings.knowledge_queue, "clipforge-knowledge")


class KnowledgeManagementApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def _enable_foreign_keys(dbapi_connection, _connection_record):
            if isinstance(dbapi_connection, sqlite3.Connection):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            future=True,
        )
        self.db = self.SessionLocal()

    def tearDown(self) -> None:
        self.db.rollback()
        self.db.close()
        with self.engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            Base.metadata.drop_all(bind=connection)
        self.engine.dispose()

    def test_upload_rejects_unsupported_extension(self) -> None:
        from backend.main import app

        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True):
            async def _run():
                async with _make_test_client(app) as client:
                    return await client.post(
                        "/api/knowledge-sources/upload",
                        files={"file": ("brand.png", b"png", "image/png")},
                    )

            response = asyncio.run(_run())

        self.assertEqual(response.status_code, 400)

    def test_upload_accepts_pdf_and_docx_extensions(self) -> None:
        from backend.main import app

        dispatched: list[str] = []
        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True), patch(
            "backend.app.knowledge.upload_service._default_dispatch_ingestion",
            side_effect=dispatched.append,
        ):
            async def _run():
                async with _make_test_client(app) as client:
                    pdf_response = await client.post(
                        "/api/knowledge-sources/upload",
                        files={"file": ("brief.pdf", _make_pdf_bytes("PDF upload"), "application/pdf")},
                    )
                    docx_response = await client.post(
                        "/api/knowledge-sources/upload",
                        files={
                            "file": (
                                "brief.docx",
                                _make_docx_bytes("DOCX upload"),
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            )
                        },
                    )
                    return pdf_response, docx_response

            pdf_response, docx_response = asyncio.run(_run())

        self.assertEqual(pdf_response.status_code, 200)
        self.assertEqual(pdf_response.json()["contentType"], "application/pdf")
        self.assertEqual(docx_response.status_code, 200)
        self.assertEqual(
            docx_response.json()["contentType"],
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        self.assertEqual(len(dispatched), 2)

    def test_get_missing_source_returns_404(self) -> None:
        from backend.main import app

        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True):
            async def _run():
                async with _make_test_client(app) as client:
                    return await client.get("/api/knowledge-sources/missing-source")

            response = asyncio.run(_run())

        self.assertEqual(response.status_code, 404)

    def test_get_source_detail_returns_summary_and_active_chunks(self) -> None:
        from backend.db.repositories import KnowledgeRepository
        from backend.main import app

        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True):
            db = self.SessionLocal()
            try:
                repo = KnowledgeRepository(db)
                source = repo.create_source(
                    id="source-detail",
                    project_key="default",
                    name="Detail Source",
                    content_type="text/markdown",
                    status="pending",
                )
                version = repo.create_version(
                    id="version-active",
                    source_id=source.id,
                    version_number=1,
                    status="uploaded",
                    content_hash="hash-v1",
                    original_filename="detail.md",
                    file_size=256,
                    parser_type="markdown",
                )
                repo.activate_version(version.id)
                repo.create_chunk(
                    id="chunk-1",
                    source_id=source.id,
                    version_id=version.id,
                    chunk_index=0,
                    chunk_type="paragraph",
                    title_path="Intro",
                    content="ClipForge uses project knowledge to ground planning decisions.",
                    token_count=9,
                    metadata_json={"section": "intro"},
                )
                repo.create_chunk(
                    id="chunk-2",
                    source_id=source.id,
                    version_id=version.id,
                    chunk_index=1,
                    chunk_type="list_block",
                    title_path="Rules",
                    content="Only active version chunks should appear in this detail response.",
                    token_count=10,
                    metadata_json={"section": "rules"},
                )
                db.commit()
            finally:
                db.close()

            async def _run():
                async with _make_test_client(app) as client:
                    return await client.get("/api/knowledge-sources/source-detail/detail")

            response = asyncio.run(_run())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"]["id"], "source-detail")
        self.assertEqual([chunk["id"] for chunk in payload["activeChunks"]], ["chunk-1", "chunk-2"])
        self.assertEqual(payload["activeChunks"][0]["versionId"], "version-active")
        self.assertEqual(payload["activeChunks"][0]["titlePath"], "Intro")
        self.assertEqual(payload["activeChunks"][0]["metadata"], {"section": "intro"})

    def test_list_source_versions_returns_version_summaries_newest_first(self) -> None:
        from backend.db.repositories import KnowledgeRepository
        from backend.main import app

        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True):
            db = self.SessionLocal()
            try:
                repo = KnowledgeRepository(db)
                source = repo.create_source(
                    id="source-versions",
                    project_key="default",
                    name="Versioned Source",
                    content_type="text/markdown",
                    status="pending",
                )
                first = repo.create_version(
                    id="version-1",
                    source_id=source.id,
                    version_number=1,
                    status="active",
                    content_hash="hash-v1",
                    original_filename="versions.md",
                    file_size=128,
                    parser_type="markdown",
                )
                second = repo.create_version(
                    id="version-2",
                    source_id=source.id,
                    version_number=2,
                    status="failed",
                    content_hash="hash-v2",
                    original_filename="versions.md",
                    file_size=256,
                    parser_type="markdown",
                )
                repo.mark_version_failed(second.id, "parser failed")
                expected_ids = [second.id, first.id]
                db.commit()
            finally:
                db.close()

            async def _run():
                async with _make_test_client(app) as client:
                    return await client.get("/api/knowledge-sources/source-versions/versions")

            response = asyncio.run(_run())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload], expected_ids)
        self.assertEqual(payload[0]["versionNumber"], 2)
        self.assertEqual(payload[0]["reason"], "parser failed")

    def test_retry_failed_source_requeues_last_failed_version(self) -> None:
        from backend.db.repositories import KnowledgeRepository
        from backend.main import app

        dispatched: list[str] = []

        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True):
            db = self.SessionLocal()
            try:
                repo = KnowledgeRepository(db)
                source = repo.create_source(
                    id="source-retry",
                    project_key="default",
                    name="Retry Source",
                    content_type="text/markdown",
                    status="pending",
                )
                version = repo.create_version(
                    id="version-retry",
                    source_id=source.id,
                    version_number=1,
                    status="uploaded",
                    content_hash="hash-v1",
                    original_filename="retry.md",
                    file_size=128,
                    parser_type="markdown",
                )
                repo.mark_version_failed(version.id, "parser failed")
                db.commit()
            finally:
                db.close()

            with patch(
                "backend.app.knowledge.source_retry_service.dispatch_knowledge_version_ingestion",
                side_effect=dispatched.append,
            ):
                async def _run():
                    async with _make_test_client(app) as client:
                        return await client.post("/api/knowledge-sources/source-retry/retry")

                response = asyncio.run(_run())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], "source-retry")
        self.assertEqual(payload["status"], "pending")
        self.assertEqual(payload["processingVersion"]["id"], "version-retry")
        self.assertEqual(payload["errorSummary"], None)
        self.assertEqual(dispatched, ["version-retry"])

    def test_retry_ready_source_returns_conflict_without_dispatch(self) -> None:
        from backend.db.repositories import KnowledgeRepository
        from backend.main import app

        dispatched: list[str] = []

        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True):
            db = self.SessionLocal()
            try:
                repo = KnowledgeRepository(db)
                repo.create_source(
                    id="source-ready",
                    project_key="default",
                    name="Ready Source",
                    content_type="text/markdown",
                    status="ready",
                )
                db.commit()
            finally:
                db.close()

            with patch(
                "backend.app.knowledge.source_retry_service.dispatch_knowledge_version_ingestion",
                side_effect=dispatched.append,
            ):
                async def _run():
                    async with _make_test_client(app) as client:
                        return await client.post("/api/knowledge-sources/source-ready/retry")

                response = asyncio.run(_run())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(dispatched, [])

    def test_list_sources_returns_summaries(self) -> None:
        from backend.db.repositories import KnowledgeRepository
        from backend.main import app

        with patch("backend.api.knowledge.SessionLocal", self.SessionLocal, create=True):
            db = self.SessionLocal()
            try:
                repo = KnowledgeRepository(db)
                newer = repo.create_source(
                    id="source-2",
                    project_key="default",
                    name="Newer Source",
                    content_type="text/markdown",
                    status="ready",
                )
                older = repo.create_source(
                    id="source-1",
                    project_key="default",
                    name="Older Source",
                    content_type="text/markdown",
                    status="ready",
                )
                deleted = repo.create_source(
                    id="source-deleted",
                    project_key="default",
                    name="Deleted Source",
                    content_type="text/markdown",
                    status="deleted",
                )
                repo.mark_source_deleted(deleted.id)
                db.flush()
                older.updated_at = newer.updated_at
                db.flush()
                expected_ids = [newer.id, older.id]
                deleted_id = deleted.id
                db.commit()
            finally:
                db.close()

            async def _run():
                async with _make_test_client(app) as client:
                    return await client.get("/api/knowledge-sources")

            response = asyncio.run(_run())

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual([item["id"] for item in payload], expected_ids)
        self.assertEqual([item["name"] for item in payload], ["Newer Source", "Older Source"])
        self.assertNotIn(deleted_id, [item["id"] for item in payload])


if __name__ == "__main__":
    unittest.main()
