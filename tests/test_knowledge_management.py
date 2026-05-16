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
from pathlib import Path
from unittest.mock import patch

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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

    def test_backend_main_registers_knowledge_router_under_api_prefix(self):
        module = importlib.import_module("backend.main")
        paths = {route.path for route in module.app.routes}

        self.assertIn("/api/knowledge-sources/upload", paths)
        self.assertIn("/api/knowledge-sources/{source_id}", paths)

    def test_upload_endpoint_declares_upload_file_shape(self):
        from fastapi import UploadFile

        route = self._get_route("/knowledge-sources/upload", "POST")
        parameter = inspect.signature(route.endpoint).parameters["file"]

        self.assertIs(parameter.annotation, UploadFile)
        self.assertEqual(parameter.default.media_type, "multipart/form-data")

    def test_upload_endpoint_raises_not_implemented_for_file_upload_calls(self):
        from fastapi import HTTPException, UploadFile

        route = self._get_route("/knowledge-sources/upload", "POST")
        upload = UploadFile(filename="knowledge.txt", file=BytesIO(b"hello"))

        with self.assertRaises(HTTPException) as context:
            asyncio.run(route.endpoint(file=upload))

        self.assertEqual(context.exception.status_code, 501)

    def test_knowledge_get_endpoint_returns_not_implemented(self):
        from fastapi import HTTPException

        route = self._get_route("/knowledge-sources/{source_id}", "GET")

        with self.assertRaises(HTTPException) as context:
            asyncio.run(route.endpoint(source_id="source-123"))

        self.assertEqual(context.exception.status_code, 501)

    def test_knowledge_delete_endpoint_returns_not_implemented(self):
        from fastapi import HTTPException

        route = self._get_route("/knowledge-sources/{source_id}", "DELETE")

        with self.assertRaises(HTTPException) as context:
            asyncio.run(route.endpoint(source_id="source-123"))

        self.assertEqual(context.exception.status_code, 501)


class KnowledgeManagementPersistenceTests(unittest.TestCase):
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
        Base.metadata.drop_all(bind=self.engine)
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


if __name__ == "__main__":
    unittest.main()
