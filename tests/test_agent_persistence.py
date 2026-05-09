import importlib
import importlib.util
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import sessionmaker


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ConfigTests(unittest.TestCase):
    def _load_settings(self, env):
        with patch.dict("os.environ", env, clear=True):
            from backend.config import get_settings

            get_settings.cache_clear()
            settings = get_settings()
            get_settings.cache_clear()
            return settings

    def test_database_and_celery_settings_can_be_loaded(self):
        env = {
            "CLIPFORGE_DATABASE_URL": "postgresql+psycopg://clipforge:secret@localhost:5432/clipforge",
            "CLIPFORGE_REDIS_URL": "redis://localhost:6379/0",
            "CELERY_BROKER_URL": "redis://localhost:6379/1",
            "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
        }

        settings = self._load_settings(env)

        self.assertEqual(settings.database_url, env["CLIPFORGE_DATABASE_URL"])
        self.assertEqual(settings.redis_url, env["CLIPFORGE_REDIS_URL"])
        self.assertEqual(settings.celery_broker_url, env["CELERY_BROKER_URL"])
        self.assertEqual(settings.celery_result_backend, env["CELERY_RESULT_BACKEND"])

    def test_celery_settings_follow_clipforge_redis_by_default(self):
        env = {
            "CLIPFORGE_REDIS_URL": "redis://localhost:6379/9",
        }

        settings = self._load_settings(env)

        self.assertEqual(settings.redis_url, env["CLIPFORGE_REDIS_URL"])
        self.assertEqual(settings.celery_broker_url, env["CLIPFORGE_REDIS_URL"])
        self.assertEqual(settings.celery_result_backend, env["CLIPFORGE_REDIS_URL"])

    def test_generic_database_and_redis_variables_are_used_as_fallback(self):
        env = {
            "DATABASE_URL": "postgresql+psycopg://fallback:user@localhost:5432/fallback",
            "REDIS_URL": "redis://localhost:6379/5",
        }

        settings = self._load_settings(env)

        self.assertEqual(settings.database_url, env["DATABASE_URL"])
        self.assertEqual(settings.redis_url, env["REDIS_URL"])
        self.assertEqual(settings.celery_broker_url, env["REDIS_URL"])
        self.assertEqual(settings.celery_result_backend, env["REDIS_URL"])

    def test_clipforge_variables_take_precedence_over_generic_fallbacks(self):
        env = {
            "CLIPFORGE_DATABASE_URL": "postgresql+psycopg://primary:user@localhost:5432/primary",
            "DATABASE_URL": "postgresql+psycopg://fallback:user@localhost:5432/fallback",
            "CLIPFORGE_REDIS_URL": "redis://localhost:6379/7",
            "REDIS_URL": "redis://localhost:6379/8",
        }

        settings = self._load_settings(env)

        self.assertEqual(settings.database_url, env["CLIPFORGE_DATABASE_URL"])
        self.assertEqual(settings.redis_url, env["CLIPFORGE_REDIS_URL"])
        self.assertEqual(settings.celery_broker_url, env["CLIPFORGE_REDIS_URL"])
        self.assertEqual(settings.celery_result_backend, env["CLIPFORGE_REDIS_URL"])

    def test_database_and_redis_settings_use_defaults_when_unset(self):
        settings = self._load_settings({})

        self.assertEqual(
            settings.database_url,
            "postgresql+psycopg://clipforge:clipforge@localhost:5432/clipforge",
        )
        self.assertEqual(settings.redis_url, "redis://localhost:6379/0")
        self.assertEqual(settings.celery_broker_url, "redis://localhost:6379/0")
        self.assertEqual(settings.celery_result_backend, "redis://localhost:6379/0")

    def test_planner_settings_support_default_and_override(self):
        env = {}
        settings = self._load_settings(env)
        self.assertEqual(settings.planner_mode, "deterministic")
        self.assertEqual(settings.planner_model, "gpt-4o-mini")

        env = {
            "CLIPFORGE_PLANNER_MODE": "openai",
            "CLIPFORGE_PLANNER_MODEL": "gpt-4.1",
        }
        settings = self._load_settings(env)
        self.assertEqual(settings.planner_mode, "openai")
        self.assertEqual(settings.planner_model, "gpt-4.1")


class DatabaseSessionTests(unittest.TestCase):
    def _load_db_package(self):
        env = {
            "CLIPFORGE_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        }

        with patch.dict("os.environ", env, clear=True):
            for module_name in ["backend.config", "backend.db.session", "backend.db"]:
                sys.modules.pop(module_name, None)

            from backend.config import get_settings

            get_settings.cache_clear()
            backend_db = importlib.import_module("backend.db")

            return {
                "Base": backend_db.Base,
                "SessionLocal": backend_db.SessionLocal,
                "create_engine_from_settings": backend_db.create_engine_from_settings,
                "engine": backend_db.engine,
            }

    def test_session_factory_is_exposed(self):
        backend_db = self._load_db_package()
        SessionLocal = backend_db["SessionLocal"]
        create_engine_from_settings = backend_db["create_engine_from_settings"]
        engine = backend_db["engine"]

        session = SessionLocal()
        try:
            self.assertIs(session.bind, engine)
        finally:
            session.close()

        self.assertTrue(callable(create_engine_from_settings))

    def test_database_engine_uses_expected_runtime_options(self):
        backend_db = self._load_db_package()
        SessionLocal = backend_db["SessionLocal"]
        engine = backend_db["engine"]

        self.assertTrue(getattr(engine.pool, "_pre_ping", False))
        self.assertTrue(SessionLocal.kw.get("future"))


class AgentPersistenceModelTests(unittest.TestCase):
    def _load_db_with_models_registered(self):
        env = {
            "CLIPFORGE_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        }

        with patch.dict("os.environ", env, clear=True):
            for module_name in ["backend.db.models", "backend.db.base", "backend.db.session", "backend.db"]:
                sys.modules.pop(module_name, None)

            return importlib.import_module("backend.db")

    def _load_models_module(self):
        if "backend.db.models" in sys.modules:
            return sys.modules["backend.db.models"]

        env = {
            "CLIPFORGE_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        }

        with patch.dict("os.environ", env, clear=True):
            for module_name in ["backend.db.models", "backend.db.base", "backend.db.session", "backend.db"]:
                sys.modules.pop(module_name, None)

            return importlib.import_module("backend.db.models")

    def test_agent_persistence_models_can_be_imported(self):
        models = self._load_models_module()

        self.assertIsNotNone(models.AgentSessionRecord)
        self.assertIsNotNone(models.AgentMessageRecord)
        self.assertIsNotNone(models.AgentPlanRecord)
        self.assertIsNotNone(models.AgentObservationRecord)
        self.assertIsNotNone(models.AgentJobRecord)
        self.assertIsNotNone(models.AgentEventRecord)
        self.assertIsNotNone(models.AgentArtifactRecord)

    def test_agent_persistence_tables_are_registered_on_base_metadata(self):
        backend_db = self._load_db_with_models_registered()
        Base = backend_db.Base
        models = backend_db.models

        tables = Base.metadata.tables

        self.assertIs(tables["agent_sessions"], models.AgentSessionRecord.__table__)
        self.assertIs(tables["agent_messages"], models.AgentMessageRecord.__table__)
        self.assertIs(tables["agent_plans"], models.AgentPlanRecord.__table__)
        self.assertIs(tables["agent_observations"], models.AgentObservationRecord.__table__)
        self.assertIs(tables["agent_jobs"], models.AgentJobRecord.__table__)
        self.assertIs(tables["agent_events"], models.AgentEventRecord.__table__)
        self.assertIs(tables["agent_artifacts"], models.AgentArtifactRecord.__table__)

    def test_agent_persistence_models_expose_required_columns(self):
        models = self._load_models_module()

        self.assertEqual(
            set(models.AgentSessionRecord.__table__.columns.keys()),
            {
                "id",
                "status",
                "current_step",
                "progress",
                "title",
                "video_url",
                "error_message",
                "error_retryable_step",
                "active_job_id",
                "current_plan_id",
                "planner_trace_json",
                "grounding_status",
                "grounding_summary_json",
                "selected_candidate_ids_json",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(
            set(models.AgentMessageRecord.__table__.columns.keys()),
            {
                "id",
                "session_id",
                "role",
                "content",
                "created_at",
            },
        )
        self.assertEqual(
            set(models.AgentPlanRecord.__table__.columns.keys()),
            {
                "id",
                "session_id",
                "version",
                "title",
                "target_duration",
                "style",
                "plan_json",
                "parent_plan_id",
                "trigger_type",
                "planner_mode",
                "planner_model",
                "execution_plan_json",
                "change_summary",
                "status",
                "created_at",
            },
        )
        self.assertEqual(
            set(models.AgentObservationRecord.__table__.columns.keys()),
            {
                "id",
                "session_id",
                "plan_id",
                "observation_type",
                "summary",
                "payload_json",
                "source_message_id",
                "source_job_id",
                "created_at",
            },
        )
        self.assertEqual(
            set(models.AgentJobRecord.__table__.columns.keys()),
            {
                "id",
                "session_id",
                "plan_id",
                "job_type",
                "status",
                "attempt_count",
                "max_attempts",
                "progress",
                "current_step",
                "error_message",
                "worker_id",
                "started_at",
                "finished_at",
                "created_at",
                "updated_at",
            },
        )
        self.assertEqual(
            set(models.AgentEventRecord.__table__.columns.keys()),
            {
                "id",
                "session_id",
                "job_id",
                "event_type",
                "step",
                "progress",
                "message",
                "payload_json",
                "created_at",
            },
        )
        self.assertEqual(
            set(models.AgentArtifactRecord.__table__.columns.keys()),
            {
                "id",
                "session_id",
                "job_id",
                "artifact_type",
                "scene_id",
                "source_url",
                "local_path",
                "public_url",
                "duration",
                "metadata_json",
                "created_at",
            },
        )

    def test_agent_persistence_metadata_exposes_expected_indexes(self):
        backend_db = self._load_db_with_models_registered()
        metadata = backend_db.Base.metadata

        plan_indexes = {index.name: index for index in metadata.tables["agent_plans"].indexes}

        self.assertEqual(
            {index.name for index in metadata.tables["agent_messages"].indexes},
            {"idx_agent_messages_session_id_created_at"},
        )
        self.assertEqual(
            set(plan_indexes),
            {"idx_agent_plans_session_id_version"},
        )
        self.assertTrue(plan_indexes["idx_agent_plans_session_id_version"].unique)
        self.assertEqual(
            {index.name for index in metadata.tables["agent_observations"].indexes},
            {
                "idx_agent_observations_session_id_created_at",
                "idx_agent_observations_plan_id_created_at",
            },
        )
        self.assertEqual(
            {index.name for index in metadata.tables["agent_jobs"].indexes},
            {
                "idx_agent_jobs_session_id_created_at",
                "idx_agent_jobs_status_created_at",
            },
        )
        self.assertEqual(
            {index.name for index in metadata.tables["agent_events"].indexes},
            {
                "idx_agent_events_session_id_created_at",
                "idx_agent_events_job_id_created_at",
            },
        )
        self.assertEqual(
            {index.name for index in metadata.tables["agent_artifacts"].indexes},
            {
                "idx_agent_artifacts_session_id_created_at",
                "idx_agent_artifacts_job_id_artifact_type",
            },
        )

    def test_grounding_response_models_align_with_plan_contract(self):
        from backend.models import agent as models

        self.assertTrue(hasattr(models, "AgentGroundingCandidate"))
        self.assertTrue(hasattr(models, "AgentGroundingSummary"))
        self.assertEqual(
            models.AgentGroundingSummary.model_fields["status"].default,
            "pending_search",
        )
        self.assertIn("grounding", models.AgentSession.model_fields)
        self.assertIsNone(models.AgentSession.model_fields["grounding"].default)

    def test_grounding_session_record_defaults_align_with_response_contract(self):
        models = self._load_models_module()

        self.assertEqual(
            models.AgentSessionRecord.__table__.columns["grounding_status"].default.arg,
            "pending_search",
        )
        self.assertTrue(
            models.AgentSessionRecord.__table__.columns["grounding_summary_json"].default.is_callable
        )
        self.assertEqual(
            models.AgentSessionRecord.__table__.columns["grounding_summary_json"].default.arg.__name__,
            "dict",
        )
        self.assertTrue(
            models.AgentSessionRecord.__table__.columns["selected_candidate_ids_json"].default.is_callable
        )
        self.assertEqual(
            models.AgentSessionRecord.__table__.columns["selected_candidate_ids_json"].default.arg.__name__,
            "list",
        )

    def test_planner_persistence_json_columns_use_non_nullable_dict_defaults(self):
        models = self._load_models_module()

        planner_trace = models.AgentSessionRecord.__table__.columns["planner_trace_json"]
        execution_plan = models.AgentPlanRecord.__table__.columns["execution_plan_json"]
        observation_payload = models.AgentObservationRecord.__table__.columns["payload_json"]

        self.assertFalse(planner_trace.nullable)
        self.assertTrue(planner_trace.default.is_callable)
        self.assertEqual(planner_trace.default.arg.__name__, "dict")

        self.assertFalse(execution_plan.nullable)
        self.assertTrue(execution_plan.default.is_callable)
        self.assertEqual(execution_plan.default.arg.__name__, "dict")

        self.assertFalse(observation_payload.nullable)
        self.assertTrue(observation_payload.default.is_callable)
        self.assertEqual(observation_payload.default.arg.__name__, "dict")


class AlembicPersistenceTests(unittest.TestCase):
    def _load_migration_module(self, filename="20260502_create_agent_tables.py"):
        migration_path = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / filename
        )
        fake_alembic = types.ModuleType("alembic")
        fake_alembic.op = _FakeAlembicOp()
        spec = importlib.util.spec_from_file_location(
            "clipforge_test_migration",
            migration_path,
        )
        module = importlib.util.module_from_spec(spec)

        with patch.dict(sys.modules, {"alembic": fake_alembic}, clear=False):
            spec.loader.exec_module(module)

        return module, fake_alembic.op

    def test_alembic_scaffold_files_exist(self):
        alembic_ini = ROOT / "backend" / "alembic.ini"
        env_py = ROOT / "backend" / "alembic" / "env.py"
        script_template = ROOT / "backend" / "alembic" / "script.py.mako"
        migration = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260502_create_agent_tables.py"
        )
        planner_persistence_migration = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260508_add_planner_persistence_foundations.py"
        )

        self.assertTrue(alembic_ini.exists())
        self.assertTrue(env_py.exists())
        self.assertTrue(script_template.exists())
        self.assertTrue(migration.exists())
        self.assertTrue(planner_persistence_migration.exists())

    def test_alembic_ini_uses_config_relative_paths(self):
        alembic_ini = ROOT / "backend" / "alembic.ini"

        self.assertTrue(alembic_ini.exists())
        content = alembic_ini.read_text(encoding="utf-8")

        self.assertIn("script_location = %(here)s/alembic", content)
        self.assertIn("prepend_sys_path = %(here)s/..", content)

    def test_grounding_state_migration_applies_and_reverts_three_columns_in_order(self):
        module, fake_op = self._load_migration_module("20260507_add_agent_grounding_state.py")

        module.upgrade()
        self.assertEqual(
            [call["name"] for call in fake_op.add_columns],
            [
                "grounding_status",
                "grounding_summary_json",
                "selected_candidate_ids_json",
            ],
        )

        module.downgrade()
        self.assertEqual(
            [call["name"] for call in fake_op.drop_columns],
            [
                "selected_candidate_ids_json",
                "grounding_summary_json",
                "grounding_status",
            ],
        )

    def test_initial_migration_mentions_core_tables_and_indexes(self):
        migration = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260502_create_agent_tables.py"
        )
        grounding_migration = (
            ROOT
            / "backend"
            / "alembic"
            / "versions"
            / "20260507_add_agent_grounding_state.py"
        )

        self.assertTrue(migration.exists())
        self.assertTrue(grounding_migration.exists())
        content = migration.read_text(encoding="utf-8")

        for table_name in [
            "agent_sessions",
            "agent_messages",
            "agent_plans",
            "agent_jobs",
            "agent_events",
            "agent_artifacts",
        ]:
            self.assertIn(table_name, content)

        for index_name in [
            "idx_agent_messages_session_id_created_at",
            "idx_agent_plans_session_id_version",
            "idx_agent_jobs_session_id_created_at",
            "idx_agent_jobs_status_created_at",
            "idx_agent_events_session_id_created_at",
            "idx_agent_events_job_id_created_at",
            "idx_agent_artifacts_session_id_created_at",
            "idx_agent_artifacts_job_id_artifact_type",
        ]:
            self.assertIn(index_name, content)

    def test_initial_migration_upgrade_and_downgrade_declare_expected_operations(self):
        module, fake_op = self._load_migration_module()

        module.upgrade()
        self.assertEqual(
            {call["name"] for call in fake_op.create_tables},
            {
                "agent_sessions",
                "agent_messages",
                "agent_plans",
                "agent_jobs",
                "agent_events",
                "agent_artifacts",
            },
        )
        self.assertEqual(
            {call["name"] for call in fake_op.create_indexes},
            {
                "idx_agent_messages_session_id_created_at",
                "idx_agent_plans_session_id_version",
                "idx_agent_jobs_session_id_created_at",
                "idx_agent_jobs_status_created_at",
                "idx_agent_events_session_id_created_at",
                "idx_agent_events_job_id_created_at",
                "idx_agent_artifacts_session_id_created_at",
                "idx_agent_artifacts_job_id_artifact_type",
            },
        )
        self.assertEqual(
            {call["name"] for call in fake_op.create_foreign_keys},
            {"fk_agent_sessions_active_job_id"},
        )

        module.downgrade()
        self.assertEqual(
            {call["name"] for call in fake_op.drop_indexes},
            {
                "idx_agent_messages_session_id_created_at",
                "idx_agent_plans_session_id_version",
                "idx_agent_jobs_session_id_created_at",
                "idx_agent_jobs_status_created_at",
                "idx_agent_events_session_id_created_at",
                "idx_agent_events_job_id_created_at",
                "idx_agent_artifacts_session_id_created_at",
                "idx_agent_artifacts_job_id_artifact_type",
            },
        )
        self.assertEqual(
            {call["name"] for call in fake_op.drop_constraints},
            {"fk_agent_sessions_active_job_id"},
        )
        self.assertEqual(
            [call["name"] for call in fake_op.drop_tables],
            [
                "agent_artifacts",
                "agent_events",
                "agent_jobs",
                "agent_plans",
                "agent_messages",
                "agent_sessions",
            ],
        )

    def test_planner_persistence_migration_declares_schema_changes_and_reversal(self):
        module, fake_op = self._load_migration_module("20260508_add_planner_persistence_foundations.py")

        module.upgrade()
        upgrade_batches = {}
        for batch in fake_op.batch_calls:
            upgrade_batches.setdefault(batch.table_name, []).append(batch)
        session_upgrade = upgrade_batches["agent_sessions"][0]
        plan_upgrade = upgrade_batches["agent_plans"][0]
        session_columns = {call["column"].name: call["column"] for call in session_upgrade.add_columns}
        plan_columns = {call["column"].name: call["column"] for call in plan_upgrade.add_columns}
        self.assertEqual(
            set(session_columns),
            {"current_plan_id", "planner_trace_json"},
        )
        self.assertEqual(
            set(plan_columns),
            {
                "parent_plan_id",
                "trigger_type",
                "planner_mode",
                "planner_model",
                "execution_plan_json",
                "change_summary",
                "status",
            },
        )
        self.assertFalse(session_columns["planner_trace_json"].nullable)
        self.assertFalse(plan_columns["execution_plan_json"].nullable)
        self.assertEqual(
            {call["name"] for call in fake_op.create_tables},
            {"agent_observations"},
        )
        self.assertEqual(
            {call["name"] for call in fake_op.create_indexes},
            {
                "idx_agent_observations_session_id_created_at",
                "idx_agent_observations_plan_id_created_at",
            },
        )
        unique_plan_index = next(
            call for call in plan_upgrade.create_indexes if call["name"] == "idx_agent_plans_session_id_version"
        )
        self.assertTrue(unique_plan_index["unique"])
        self.assertEqual(
            {call["name"] for call in session_upgrade.create_foreign_keys}
            | {call["name"] for call in plan_upgrade.create_foreign_keys},
            {
                "fk_agent_sessions_current_plan_id",
                "fk_agent_plans_parent_plan_id",
            },
        )
        self.assertEqual(len(fake_op.execute_calls), 1)

        module.downgrade()
        downgrade_batches = {}
        for batch in fake_op.batch_calls[2:]:
            downgrade_batches.setdefault(batch.table_name, []).append(batch)
        plan_downgrade = downgrade_batches["agent_plans"][0]
        session_downgrade = downgrade_batches["agent_sessions"][0]
        self.assertEqual(
            {call["name"] for call in fake_op.drop_indexes},
            {
                "idx_agent_observations_session_id_created_at",
                "idx_agent_observations_plan_id_created_at",
            },
        )
        self.assertEqual(
            {call["name"] for call in session_downgrade.drop_foreign_keys}
            | {call["name"] for call in plan_downgrade.drop_foreign_keys},
            {
                "fk_agent_sessions_current_plan_id",
                "fk_agent_plans_parent_plan_id",
            },
        )
        self.assertEqual(
            [call["name"] for call in fake_op.drop_tables],
            ["agent_observations"],
        )
        self.assertEqual(
            {call["name"] for call in plan_downgrade.drop_columns},
            {
                "status",
                "change_summary",
                "execution_plan_json",
                "planner_model",
                "planner_mode",
                "trigger_type",
                "parent_plan_id",
            },
        )
        self.assertEqual(
            {call["name"] for call in session_downgrade.drop_columns},
            {"planner_trace_json", "current_plan_id"},
        )

    def test_planner_persistence_migration_uses_recreate_only_for_sqlite(self):
        module, fake_op = self._load_migration_module("20260508_add_planner_persistence_foundations.py")
        fake_op.bind.dialect.name = "postgresql"

        module.upgrade()
        upgrade_batches = {}
        for batch in fake_op.batch_calls:
            upgrade_batches.setdefault(batch.table_name, []).append(batch)
        self.assertIsNone(upgrade_batches["agent_sessions"][0].kwargs.get("recreate"))
        self.assertIsNone(upgrade_batches["agent_plans"][0].kwargs.get("recreate"))

        module.downgrade()
        downgrade_batches = {}
        for batch in fake_op.batch_calls[2:]:
            downgrade_batches.setdefault(batch.table_name, []).append(batch)
        self.assertIsNone(downgrade_batches["agent_plans"][0].kwargs.get("recreate"))
        self.assertIsNone(downgrade_batches["agent_sessions"][0].kwargs.get("recreate"))

    def test_planner_persistence_migration_executes_and_normalizes_duplicate_versions(self):
        metadata = MetaData()
        agent_sessions = Table(
            "agent_sessions",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("status", String(32), nullable=False),
            Column("current_step", String(128), nullable=True),
            Column("progress", Float(), nullable=False),
            Column("title", String(255), nullable=True),
            Column("video_url", String(512), nullable=True),
            Column("error_message", String(), nullable=True),
            Column("error_retryable_step", String(128), nullable=True),
            Column("active_job_id", String(36), nullable=True),
            Column("grounding_status", String(32), nullable=True),
            Column("grounding_summary_json", JSON(), nullable=True),
            Column("selected_candidate_ids_json", JSON(), nullable=True),
            Column("created_at", DateTime(), nullable=False),
            Column("updated_at", DateTime(), nullable=False),
        )
        agent_messages = Table(
            "agent_messages",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("session_id", String(36), ForeignKey("agent_sessions.id"), nullable=False),
            Column("role", String(32), nullable=False),
            Column("content", String(), nullable=False),
            Column("created_at", DateTime(), nullable=False),
        )
        agent_plans = Table(
            "agent_plans",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("session_id", String(36), ForeignKey("agent_sessions.id"), nullable=False),
            Column("version", Integer(), nullable=False),
            Column("title", String(255), nullable=True),
            Column("target_duration", Integer(), nullable=True),
            Column("style", String(128), nullable=True),
            Column("plan_json", JSON(), nullable=False),
            Column("created_at", DateTime(), nullable=False),
        )
        agent_jobs = Table(
            "agent_jobs",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("session_id", String(36), ForeignKey("agent_sessions.id"), nullable=True),
            Column("plan_id", String(36), ForeignKey("agent_plans.id"), nullable=True),
            Column("job_type", String(64), nullable=False),
            Column("status", String(32), nullable=False),
            Column("attempt_count", Integer(), nullable=False),
            Column("max_attempts", Integer(), nullable=False),
            Column("progress", Float(), nullable=False),
            Column("current_step", String(128), nullable=True),
            Column("error_message", String(), nullable=True),
            Column("worker_id", String(128), nullable=True),
            Column("started_at", DateTime(), nullable=True),
            Column("finished_at", DateTime(), nullable=True),
            Column("created_at", DateTime(), nullable=False),
            Column("updated_at", DateTime(), nullable=False),
        )
        agent_events = Table(
            "agent_events",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("session_id", String(36), ForeignKey("agent_sessions.id"), nullable=True),
            Column("job_id", String(36), ForeignKey("agent_jobs.id"), nullable=True),
            Column("event_type", String(64), nullable=False),
            Column("step", String(128), nullable=True),
            Column("progress", Float(), nullable=True),
            Column("message", String(), nullable=True),
            Column("payload_json", JSON(), nullable=True),
            Column("created_at", DateTime(), nullable=False),
        )
        agent_artifacts = Table(
            "agent_artifacts",
            metadata,
            Column("id", String(36), primary_key=True),
            Column("session_id", String(36), ForeignKey("agent_sessions.id"), nullable=True),
            Column("job_id", String(36), ForeignKey("agent_jobs.id"), nullable=True),
            Column("artifact_type", String(64), nullable=False),
            Column("scene_id", String(36), nullable=True),
            Column("source_url", String(512), nullable=True),
            Column("local_path", String(512), nullable=True),
            Column("public_url", String(512), nullable=True),
            Column("duration", Float(), nullable=True),
            Column("metadata_json", JSON(), nullable=True),
            Column("created_at", DateTime(), nullable=False),
        )

        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        try:
            with engine.connect() as conn:
                conn.execute(text("PRAGMA foreign_keys=ON"))
                metadata.create_all(conn)
                conn.execute(
                    text(
                        "CREATE INDEX idx_agent_plans_session_id_version "
                        "ON agent_plans (session_id, version)"
                    )
                )
                conn.execute(
                    agent_sessions.insert(),
                    [
                        {
                            "id": "sess-1",
                            "status": "active",
                            "current_step": None,
                            "progress": 0.0,
                            "title": "会话",
                            "video_url": None,
                            "error_message": None,
                            "error_retryable_step": None,
                            "active_job_id": None,
                            "grounding_status": "pending_search",
                            "grounding_summary_json": {},
                            "selected_candidate_ids_json": [],
                            "created_at": datetime(2026, 5, 8, 0, 0, 0),
                            "updated_at": datetime(2026, 5, 8, 0, 0, 0),
                        }
                    ],
                )
                conn.execute(
                    agent_plans.insert(),
                    [
                        {
                            "id": "plan-1",
                            "session_id": "sess-1",
                            "version": 1,
                            "title": "一",
                            "target_duration": 30,
                            "style": "a",
                            "plan_json": {"steps": ["search"]},
                            "created_at": datetime(2026, 5, 8, 0, 0, 0),
                        },
                        {
                            "id": "plan-2",
                            "session_id": "sess-1",
                            "version": 1,
                            "title": "二",
                            "target_duration": 30,
                            "style": "b",
                            "plan_json": {"steps": ["render"]},
                            "created_at": datetime(2026, 5, 8, 0, 0, 1),
                        },
                        {
                            "id": "plan-3",
                            "session_id": "sess-1",
                            "version": 3,
                            "title": "三",
                            "target_duration": 30,
                            "style": "c",
                            "plan_json": {"steps": ["publish"]},
                            "created_at": datetime(2026, 5, 8, 0, 0, 2),
                        },
                    ],
                )
                conn.execute(
                    agent_messages.insert(),
                    [
                        {
                            "id": "msg-1",
                            "session_id": "sess-1",
                            "role": "user",
                            "content": "hello",
                            "created_at": datetime(2026, 5, 8, 0, 0, 0),
                        }
                    ],
                )
                conn.execute(
                    agent_jobs.insert(),
                    [
                        {
                            "id": "job-1",
                            "session_id": "sess-1",
                            "plan_id": "plan-1",
                            "job_type": "render",
                            "status": "pending",
                            "attempt_count": 0,
                            "max_attempts": 1,
                            "progress": 0.0,
                            "current_step": None,
                            "error_message": None,
                            "worker_id": None,
                            "started_at": None,
                            "finished_at": None,
                            "created_at": datetime(2026, 5, 8, 0, 0, 0),
                            "updated_at": datetime(2026, 5, 8, 0, 0, 0),
                        }
                    ],
                )
                conn.execute(
                    agent_events.insert(),
                    [
                        {
                            "id": "evt-1",
                            "session_id": "sess-1",
                            "job_id": "job-1",
                            "event_type": "job.progress",
                            "step": None,
                            "progress": 0.0,
                            "message": None,
                            "payload_json": {},
                            "created_at": datetime(2026, 5, 8, 0, 0, 0),
                        }
                    ],
                )
                conn.execute(
                    agent_artifacts.insert(),
                    [
                        {
                            "id": "art-1",
                            "session_id": "sess-1",
                            "job_id": "job-1",
                            "artifact_type": "clip",
                            "scene_id": None,
                            "source_url": None,
                            "local_path": None,
                            "public_url": None,
                            "duration": None,
                            "metadata_json": {},
                            "created_at": datetime(2026, 5, 8, 0, 0, 0),
                        }
                    ],
                )
                conn.commit()

                from alembic.operations import Operations
                from alembic.runtime.migration import MigrationContext

                migration_path = (
                    ROOT
                    / "backend"
                    / "alembic"
                    / "versions"
                    / "20260508_add_planner_persistence_foundations.py"
                )
                migration_tx = conn.begin()
                migration_context = MigrationContext.configure(conn)
                operations = Operations(migration_context)
                fake_alembic = types.ModuleType("alembic")
                fake_alembic.op = operations
                spec = importlib.util.spec_from_file_location(
                    "clipforge_real_migration",
                    migration_path,
                )
                module = importlib.util.module_from_spec(spec)

                with patch.dict(sys.modules, {"alembic": fake_alembic}, clear=False):
                    spec.loader.exec_module(module)
                    module.upgrade()

                columns = {column["name"] for column in inspect(conn).get_columns("agent_sessions")}
                self.assertIn("current_plan_id", columns)
                self.assertIn("planner_trace_json", columns)
                upgraded_versions = conn.execute(
                    text(
                        "SELECT version, execution_plan_json FROM agent_plans "
                        "WHERE session_id = 'sess-1' ORDER BY version"
                    )
                ).all()
                self.assertEqual([row[0] for row in upgraded_versions], [1, 3, 4])
                self.assertTrue(all(row[1] == "{}" for row in upgraded_versions))

                session_trace = conn.execute(
                    text("SELECT planner_trace_json FROM agent_sessions WHERE id = 'sess-1'")
                ).scalar_one()
                self.assertEqual(session_trace, "{}")

                plan_columns = {column["name"]: column for column in inspect(conn).get_columns("agent_plans")}
                session_columns = {column["name"]: column for column in inspect(conn).get_columns("agent_sessions")}
                self.assertFalse(plan_columns["execution_plan_json"]["nullable"])
                self.assertFalse(session_columns["planner_trace_json"]["nullable"])

                index_rows = conn.execute(text("PRAGMA index_list('agent_plans')")).mappings().all()
                plan_index = next(row for row in index_rows if row["name"] == "idx_agent_plans_session_id_version")
                self.assertEqual(plan_index["unique"], 1)

                module.downgrade()
                downgraded_columns = {
                    column["name"] for column in inspect(conn).get_columns("agent_sessions")
                }
                self.assertNotIn("current_plan_id", downgraded_columns)
                self.assertNotIn("planner_trace_json", downgraded_columns)
                migration_tx.commit()
        finally:
            engine.dispose()


class _FakeAlembicOp:
    def __init__(self):
        self.create_tables = []
        self.create_indexes = []
        self.create_foreign_keys = []
        self.add_columns = []
        self.execute_calls = []
        self.drop_columns = []
        self.drop_indexes = []
        self.drop_constraints = []
        self.drop_tables = []
        self.batch_calls = []
        self.bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))

    def create_table(self, name, *columns, **kwargs):
        self.create_tables.append({"name": name, "columns": columns, "kwargs": kwargs})

    def create_index(self, name, table_name, columns, **kwargs):
        self.create_indexes.append(
            {
                "name": name,
                "table_name": table_name,
                "columns": tuple(columns),
                "kwargs": kwargs,
            }
        )

    def create_foreign_key(self, name, source_table, referent_table, local_cols, remote_cols, **kwargs):
        self.create_foreign_keys.append(
            {
                "name": name,
                "source_table": source_table,
                "referent_table": referent_table,
                "local_cols": tuple(local_cols),
                "remote_cols": tuple(remote_cols),
                "kwargs": kwargs,
            }
        )

    def add_column(self, table_name, column, **kwargs):
        self.add_columns.append({"table_name": table_name, "name": column.name, "column": column, "kwargs": kwargs})

    def execute(self, statement, **kwargs):
        self.execute_calls.append({"statement": statement, "kwargs": kwargs})

    def drop_column(self, table_name, column_name, **kwargs):
        self.drop_columns.append({"table_name": table_name, "name": column_name, "kwargs": kwargs})

    def drop_index(self, name, table_name=None, **kwargs):
        self.drop_indexes.append({"name": name, "table_name": table_name, "kwargs": kwargs})

    def drop_constraint(self, name, table_name, type_=None, **kwargs):
        self.drop_constraints.append(
            {"name": name, "table_name": table_name, "type": type_, "kwargs": kwargs}
        )

    def drop_table(self, name, **kwargs):
        self.drop_tables.append({"name": name, "kwargs": kwargs})

    def batch_alter_table(self, table_name, **kwargs):
        batch = _FakeBatchAlembicOp(table_name, kwargs)
        self.batch_calls.append(batch)
        return batch

    def get_bind(self):
        return self.bind


class _FakeBatchAlembicOp:
    def __init__(self, table_name, kwargs):
        self.table_name = table_name
        self.kwargs = kwargs
        self.add_columns = []
        self.create_foreign_keys = []
        self.drop_foreign_keys = []
        self.create_indexes = []
        self.drop_indexes = []
        self.drop_columns = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_column(self, column, **kwargs):
        self.add_columns.append({"column": column, "kwargs": kwargs})

    def create_foreign_key(self, name, referent_table, local_cols, remote_cols, **kwargs):
        self.create_foreign_keys.append(
            {
                "name": name,
                "referent_table": referent_table,
                "local_cols": tuple(local_cols),
                "remote_cols": tuple(remote_cols),
                "kwargs": kwargs,
            }
        )

    def drop_constraint(self, name, type_=None, **kwargs):
        self.drop_foreign_keys.append({"name": name, "type": type_, "kwargs": kwargs})

    def drop_index(self, name, **kwargs):
        self.drop_indexes.append({"name": name, "kwargs": kwargs})

    def create_index(self, name, columns, unique=False, **kwargs):
        self.create_indexes.append(
            {
                "name": name,
                "columns": tuple(columns),
                "unique": unique,
                "kwargs": kwargs,
            }
        )

    def drop_column(self, name, **kwargs):
        self.drop_columns.append({"name": name, "kwargs": kwargs})


class RepositoryContractTests(unittest.TestCase):
    def test_repositories_expose_minimal_methods(self):
        from backend.db.repositories import (
            AgentArtifactRepository,
            AgentEventRepository,
            AgentJobRepository,
            AgentMessageRepository,
            AgentPlanRepository,
            AgentSessionRepository,
        )

        self.assertTrue(callable(getattr(AgentSessionRepository, "create", None)))
        self.assertTrue(callable(getattr(AgentSessionRepository, "get", None)))
        self.assertTrue(callable(getattr(AgentSessionRepository, "update_grounding_state", None)))
        self.assertTrue(callable(getattr(AgentMessageRepository, "create", None)))
        self.assertTrue(callable(getattr(AgentMessageRepository, "list_for_session", None)))
        self.assertTrue(callable(getattr(AgentPlanRepository, "create", None)))
        self.assertTrue(callable(getattr(AgentPlanRepository, "get_latest_for_session", None)))
        self.assertTrue(callable(getattr(AgentPlanRepository, "get", None)))
        self.assertTrue(callable(getattr(AgentJobRepository, "create", None)))
        self.assertTrue(callable(getattr(AgentJobRepository, "get", None)))
        self.assertTrue(callable(getattr(AgentJobRepository, "update_status", None)))
        self.assertTrue(callable(getattr(AgentEventRepository, "create", None)))
        self.assertTrue(callable(getattr(AgentEventRepository, "list_for_session", None)))
        self.assertTrue(callable(getattr(AgentArtifactRepository, "create", None)))
        self.assertTrue(callable(getattr(AgentArtifactRepository, "list_for_session", None)))
        self.assertTrue(callable(getattr(AgentArtifactRepository, "list_candidate_visuals_for_session", None)))


class RepositoryBehaviorTests(unittest.TestCase):
    def setUp(self):
        from backend.db.base import Base
        import backend.db.models  # noqa: F401

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        event.listen(self.engine, "connect", self._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def test_repositories_do_not_commit_writes_automatically(self):
        from backend.db.repositories import AgentJobRepository, AgentPlanRepository, AgentSessionRepository

        session_repo = AgentSessionRepository(self.db)
        session_record = session_repo.create(title="未提交会话")

        self.assertIsNotNone(session_record.id)
        self.assertTrue(self.db.in_transaction())
        self.db.rollback()
        self.assertIsNone(session_repo.get(session_record.id))

        session_record = session_repo.create(title="任务事务测试")
        plan_repo = AgentPlanRepository(self.db)
        plan_record = plan_repo.create(
            session_id=session_record.id,
            version=1,
            title="事务计划",
            plan_json={"steps": []},
        )
        job_repo = AgentJobRepository(self.db)
        job_record = job_repo.create(
            session_id=session_record.id,
            plan_id=plan_record.id,
            job_type="render",
            status="pending",
        )
        updated_job = job_repo.update_status(job_record.id, status="running")

        self.assertEqual(updated_job.status, "running")
        self.assertTrue(self.db.in_transaction())
        self.db.rollback()
        self.assertIsNone(job_repo.get(job_record.id))

    def test_repositories_support_basic_create_get_list_and_update(self):
        from backend.db.repositories import (
            AgentArtifactRepository,
            AgentEventRepository,
            AgentJobRepository,
            AgentMessageRepository,
            AgentPlanRepository,
            AgentSessionRepository,
        )

        session_repo = AgentSessionRepository(self.db)
        message_repo = AgentMessageRepository(self.db)
        plan_repo = AgentPlanRepository(self.db)
        job_repo = AgentJobRepository(self.db)
        event_repo = AgentEventRepository(self.db)
        artifact_repo = AgentArtifactRepository(self.db)

        session_record = session_repo.create(title="测试会话", status="draft")
        self.db.commit()
        self.assertEqual(session_repo.get(session_record.id).title, "测试会话")

        message_record = message_repo.create(
            session_id=session_record.id,
            role="user",
            content="帮我做一个 30 秒视频",
        )
        self.db.commit()
        self.assertEqual(message_record.session_id, session_record.id)
        self.assertEqual(len(message_repo.list_for_session(session_record.id)), 1)

        plan_v1 = plan_repo.create(
            session_id=session_record.id,
            version=1,
            title="第一版方案",
            target_duration=30,
            style="快节奏",
            plan_json={"steps": ["search"]},
        )
        self.db.commit()
        plan_v2 = plan_repo.create(
            session_id=session_record.id,
            version=2,
            title="第二版方案",
            target_duration=45,
            style="叙事",
            plan_json={"steps": ["search", "render"]},
        )
        self.db.commit()
        self.assertEqual(plan_repo.get(plan_v1.id).title, "第一版方案")
        self.assertEqual(plan_repo.get_latest_for_session(session_record.id).id, plan_v2.id)

        job_record = job_repo.create(
            session_id=session_record.id,
            plan_id=plan_v2.id,
            job_type="render",
            status="pending",
        )
        updated_job = job_repo.update_status(
            job_record.id,
            status="running",
            current_step="download",
            progress=0.5,
        )
        self.db.commit()
        self.assertEqual(job_repo.get(job_record.id).status, "running")
        self.assertEqual(updated_job.current_step, "download")
        self.assertEqual(updated_job.progress, 0.5)

        event_repo.create(
            session_id=session_record.id,
            job_id=job_record.id,
            event_type="job.progress",
            step="download",
            progress=0.5,
            message="正在下载素材",
            payload_json={"percent": 50},
        )
        self.db.commit()
        self.assertEqual(len(event_repo.list_for_session(session_record.id)), 1)

        artifact_repo.create(
            session_id=session_record.id,
            job_id=job_record.id,
            artifact_type="clip",
            local_path="/tmp/test.mp4",
            public_url="/output/test.mp4",
        )
        self.db.commit()
        artifacts = artifact_repo.list_for_session(session_record.id)
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(artifacts[0].artifact_type, "clip")

        session_repo.update_grounding_state(
            session_record.id,
            grounding_status="confirmed",
            grounding_summary_json={"status": "confirmed", "candidates": [{"id": "fixture:1"}]},
            selected_candidate_ids_json=["fixture:1"],
        )
        artifact_repo.create(
            session_id=session_record.id,
            job_id=job_record.id,
            artifact_type="candidate_visual",
            public_url="/output/candidate.jpg",
        )
        self.db.commit()

        updated_session = session_repo.get(session_record.id)
        self.assertEqual(updated_session.grounding_status, "confirmed")
        self.assertEqual(updated_session.selected_candidate_ids_json, ["fixture:1"])
        candidate_artifacts = artifact_repo.list_candidate_visuals_for_session(session_record.id)
        self.assertEqual(len(candidate_artifacts), 1)
        self.assertEqual(candidate_artifacts[0].artifact_type, "candidate_visual")

    def test_update_status_returns_none_for_missing_job(self):
        from backend.db.repositories import AgentJobRepository

        job_repo = AgentJobRepository(self.db)

        self.assertIsNone(job_repo.update_status("missing-job-id", status="failed"))

    def test_update_status_rejects_unknown_fields(self):
        from backend.db.repositories import AgentJobRepository, AgentPlanRepository, AgentSessionRepository

        session_repo = AgentSessionRepository(self.db)
        plan_repo = AgentPlanRepository(self.db)
        job_repo = AgentJobRepository(self.db)

        session_record = session_repo.create(title="任务测试")
        self.db.commit()
        plan_record = plan_repo.create(
            session_id=session_record.id,
            version=1,
            title="计划",
            plan_json={"steps": []},
        )
        self.db.commit()
        job_record = job_repo.create(
            session_id=session_record.id,
            plan_id=plan_record.id,
            job_type="render",
            status="pending",
        )
        self.db.commit()

        with self.assertRaises(ValueError):
            job_repo.update_status(job_record.id, job_type="search")

    def test_list_for_session_uses_stable_ordering(self):
        from backend.db.repositories import (
            AgentArtifactRepository,
            AgentEventRepository,
            AgentMessageRepository,
            AgentPlanRepository,
            AgentSessionRepository,
        )

        session_repo = AgentSessionRepository(self.db)
        message_repo = AgentMessageRepository(self.db)
        event_repo = AgentEventRepository(self.db)
        artifact_repo = AgentArtifactRepository(self.db)
        plan_repo = AgentPlanRepository(self.db)

        session_record = session_repo.create(title="排序测试")
        self.db.commit()

        message_b = message_repo.create(
            id="msg-b",
            session_id=session_record.id,
            role="assistant",
            content="第二条",
        )
        message_a = message_repo.create(
            id="msg-a",
            session_id=session_record.id,
            role="user",
            content="第一条",
        )
        fixed_time = message_b.created_at
        message_a.created_at = fixed_time
        message_b.created_at = fixed_time
        self.db.flush()
        self.db.commit()
        self.assertEqual(
            [message.id for message in message_repo.list_for_session(session_record.id)],
            ["msg-a", "msg-b"],
        )

        event_b = event_repo.create(
            id="evt-b",
            session_id=session_record.id,
            event_type="job.progress",
        )
        event_a = event_repo.create(
            id="evt-a",
            session_id=session_record.id,
            event_type="job.progress",
        )
        fixed_event_time = event_b.created_at
        event_a.created_at = fixed_event_time
        event_b.created_at = fixed_event_time
        self.db.flush()
        self.db.commit()
        self.assertEqual(
            [event.id for event in event_repo.list_for_session(session_record.id)],
            ["evt-a", "evt-b"],
        )

        artifact_b = artifact_repo.create(
            id="art-b",
            session_id=session_record.id,
            artifact_type="clip",
        )
        artifact_a = artifact_repo.create(
            id="art-a",
            session_id=session_record.id,
            artifact_type="clip",
        )
        fixed_artifact_time = artifact_b.created_at
        artifact_a.created_at = fixed_artifact_time
        artifact_b.created_at = fixed_artifact_time
        self.db.flush()
        self.db.commit()
        self.assertEqual(
            [artifact.id for artifact in artifact_repo.list_for_session(session_record.id)],
            ["art-a", "art-b"],
        )

        plan_v2 = plan_repo.create(
            id="plan-v2",
            session_id=session_record.id,
            version=2,
            title="第二版",
            plan_json={"steps": ["render"]},
        )
        plan_v1 = plan_repo.create(
            id="plan-v1",
            session_id=session_record.id,
            version=1,
            title="第一版",
            plan_json={"steps": ["search"]},
        )
        fixed_plan_time = plan_v2.created_at
        plan_v1.created_at = fixed_plan_time
        plan_v2.created_at = fixed_plan_time
        self.db.flush()
        self.db.commit()
        self.assertEqual(
            [plan.id for plan in plan_repo.list_for_session(session_record.id)],
            ["plan-v1", "plan-v2"],
        )

    def test_get_latest_for_session_prefers_highest_version(self):
        from backend.db.repositories import AgentPlanRepository, AgentSessionRepository

        session_repo = AgentSessionRepository(self.db)
        plan_repo = AgentPlanRepository(self.db)

        session_record = session_repo.create(title="计划排序测试")
        self.db.commit()

        plan_a = plan_repo.create(
            id="plan-a",
            session_id=session_record.id,
            version=2,
            title="A",
            plan_json={"steps": []},
        )
        plan_b = plan_repo.create(
            id="plan-b",
            session_id=session_record.id,
            version=3,
            title="B",
            plan_json={"steps": []},
        )
        fixed_plan_time = plan_a.created_at
        plan_a.created_at = fixed_plan_time
        plan_b.created_at = fixed_plan_time
        self.db.flush()
        self.db.commit()

        self.assertEqual(plan_repo.get_latest_for_session(session_record.id).id, "plan-b")

    def test_agent_observation_repository_persists_defaults_and_lists_in_time_order(self):
        from backend.db.repositories import (
            AgentObservationRepository,
            AgentPlanRepository,
            AgentSessionRepository,
        )

        session_repo = AgentSessionRepository(self.db)
        plan_repo = AgentPlanRepository(self.db)
        observation_repo = AgentObservationRepository(self.db)

        session_record = session_repo.create(
            id="obs-session",
            title="观察测试",
            planner_trace_json={},
        )
        plan_record = plan_repo.create(
            id="obs-plan",
            session_id=session_record.id,
            version=1,
            title="观察计划",
            plan_json={"steps": []},
            execution_plan_json={},
        )
        older = observation_repo.create(
            id="obs-b",
            session_id=session_record.id,
            plan_id=plan_record.id,
            observation_type="planner.note",
            summary="后写入但排前面",
        )
        newer = observation_repo.create(
            id="obs-a",
            session_id=session_record.id,
            plan_id=plan_record.id,
            observation_type="planner.note",
            summary="先写入但排后面",
            payload_json={"source": "user"},
        )
        fixed_time = older.created_at
        older.created_at = fixed_time
        newer.created_at = fixed_time
        self.db.flush()
        self.db.commit()

        self.assertEqual(older.payload_json, {})
        self.assertEqual(newer.payload_json, {"source": "user"})
        self.assertEqual(
            [record.id for record in observation_repo.list_for_session(session_record.id)],
            ["obs-a", "obs-b"],
        )

    def test_agent_session_repository_normalizes_planner_trace_none_to_empty_dict(self):
        from backend.db.repositories import AgentSessionRepository

        session_repo = AgentSessionRepository(self.db)
        session_record = session_repo.create(
            id="session-trace",
            title="planner trace",
            planner_trace_json=None,
        )
        self.db.commit()

        self.assertEqual(session_repo.get(session_record.id).planner_trace_json, {})

    def test_agent_plan_versions_are_unique_per_session(self):
        from sqlalchemy.exc import IntegrityError
        from backend.db.repositories import AgentPlanRepository, AgentSessionRepository

        session_repo = AgentSessionRepository(self.db)
        plan_repo = AgentPlanRepository(self.db)

        session_record = session_repo.create(title="唯一版本测试")
        self.db.commit()
        plan_repo.create(
            session_id=session_record.id,
            version=1,
            title="第一版",
            plan_json={"steps": []},
        )
        self.db.commit()

        with self.assertRaises(IntegrityError):
            plan_repo.create(
                session_id=session_record.id,
                version=1,
                title="重复版",
                plan_json={"steps": []},
            )
            self.db.commit()

    def test_sqlite_foreign_keys_are_enabled(self):
        result = self.db.execute(text("PRAGMA foreign_keys")).scalar_one()
        self.assertEqual(result, 1)


class SessionServiceContractTests(unittest.TestCase):
    def test_agent_session_service_exposes_minimal_methods(self):
        from backend.services.agent_session_service import AgentSessionService

        self.assertTrue(callable(getattr(AgentSessionService, "create_session", None)))
        self.assertTrue(callable(getattr(AgentSessionService, "get_session", None)))
        self.assertTrue(callable(getattr(AgentSessionService, "add_user_message", None)))

    def test_agent_read_service_exposes_read_methods(self):
        from backend.services.agent_read_service import AgentReadService

        self.assertTrue(callable(getattr(AgentReadService, "read_session", None)))
        self.assertTrue(callable(getattr(AgentReadService, "load_latest_plan", None)))
        self.assertTrue(callable(getattr(AgentReadService, "load_artifacts", None)))
        self.assertTrue(callable(getattr(AgentReadService, "build_session_response", None)))


class SessionServiceBehaviorTests(unittest.TestCase):
    def setUp(self):
        from backend.db.base import Base
        import backend.db.models  # noqa: F401

        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        event.listen(self.engine, "connect", RepositoryBehaviorTests._enable_sqlite_foreign_keys)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, future=True)

    def tearDown(self):
        self.engine.dispose()

    def test_agent_session_schema_includes_events_and_active_job_id(self):
        from backend.models.agent import AgentEvent, AgentSession

        self.assertIn("events", AgentSession.model_fields)
        self.assertIn("activeJobId", AgentSession.model_fields)
        self.assertEqual(AgentSession.model_fields["events"].default_factory(), [])
        self.assertIsNone(AgentSession.model_fields["activeJobId"].default)
        self.assertIn("message", AgentEvent.model_fields)

    def test_create_session_with_prompt_persists_session_message_and_initial_plan(self):
        from backend.db.repositories import (
            AgentMessageRepository,
            AgentObservationRepository,
            AgentPlanRepository,
            AgentSessionRepository,
        )
        from backend.models.agent import AgentStatus
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        session = service.create_session("做一个 30 秒科技短片")

        self.assertEqual(session.status, AgentStatus.PLAN_READY)
        self.assertEqual(len(session.messages), 2)
        self.assertEqual(session.messages[0].role, "user")
        self.assertEqual(session.messages[1].role, "assistant")
        self.assertIsNotNone(session.plan)
        self.assertIsNone(session.grounding)
        self.assertEqual(session.currentStep, "剪辑方案已生成")
        self.assertEqual(session.progress, 20)

        db = self.SessionLocal()
        try:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            plan_repo = AgentPlanRepository(db)
            observation_repo = AgentObservationRepository(db)

            session_record = session_repo.get(session.id)
            self.assertEqual(session_record.status, "plan_ready")
            self.assertIsNone(session_record.grounding_status)
            self.assertEqual(len(message_repo.list_for_session(session.id)), 2)
            self.assertIsNotNone(plan_repo.get_latest_for_session(session.id))
            self.assertEqual(len(observation_repo.list_for_session(session.id)), 1)
        finally:
            db.close()

    def test_read_service_builds_agent_session_from_database_rows(self):
        from backend.db.repositories import (
            AgentArtifactRepository,
            AgentEventRepository,
            AgentJobRepository,
            AgentPlanRepository,
            AgentSessionRepository,
        )
        from backend.models.agent import AgentStatus
        from backend.services.agent_read_service import AgentReadService

        db = self.SessionLocal()
        try:
            session_repo = AgentSessionRepository(db)
            plan_repo = AgentPlanRepository(db)
            job_repo = AgentJobRepository(db)
            event_repo = AgentEventRepository(db)
            artifact_repo = AgentArtifactRepository(db)

            session_record = session_repo.create(
                status="plan_ready",
                current_step="剪辑方案已生成",
                progress=20,
                title="数据库会话",
                active_job_id=None,
            )
            session_id = session_record.id
            plan_repo.create(
                session_id=session_id,
                version=1,
                title="数据库会话",
                target_duration=30,
                style="快节奏社媒短片",
                plan_json={
                    "title": "数据库会话",
                    "targetDuration": 30,
                    "style": "快节奏社媒短片",
                    "scenes": [
                        {
                            "id": 1,
                            "description": "开场建立氛围",
                            "keywords": ["technology"],
                            "duration": 6,
                            "searchQuery": "technology",
                        }
                    ],
                },
            )
            job_record = job_repo.create(
                session_id=session_id,
                job_type="render",
                status="running",
            )
            job_id = job_record.id
            session_record.active_job_id = job_id
            event_repo.create(
                session_id=session_id,
                job_id=job_id,
                event_type="job.progress",
                message="正在渲染",
                progress=0.8,
            )
            artifact_repo.create(
                session_id=session_id,
                job_id=job_id,
                artifact_type="clip",
                scene_id="1",
                source_url="https://example.com/source.mp4",
                local_path="/tmp/source.mp4",
                public_url="/output/source.mp4",
                duration=6.0,
            )
            db.commit()
        finally:
            db.close()

        read_service = AgentReadService(session_factory=self.SessionLocal)
        session = read_service.read_session(session_id)

        self.assertEqual(session.status, AgentStatus.PLAN_READY)
        self.assertEqual(session.activeJobId, job_id)
        self.assertEqual(session.plan.title, "数据库会话")
        self.assertEqual(len(session.clips), 1)
        self.assertEqual(session.clips[0].publicUrl, "/output/source.mp4")
        self.assertEqual(len(session.events), 1)
        self.assertEqual(session.events[0].message, "正在渲染")

    def test_add_user_message_persists_message_and_merges_grounding_context_until_confirmed(self):
        from backend.db.repositories import AgentMessageRepository, AgentPlanRepository, AgentSessionRepository
        from backend.models.agent import AgentStatus
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        session = service.create_session()
        first = service.add_user_message(session.id, "给 Notion AI 做一个 30 秒产品亮点视频")
        updated = service.add_user_message(session.id, "整体再商务一点，目标受众改成销售团队")

        self.assertEqual(updated.status, AgentStatus.PLAN_READY)
        self.assertIsNone(updated.plan)
        self.assertIsNotNone(updated.grounding)
        self.assertEqual(updated.grounding.status, "needs_confirmation")
        self.assertEqual(updated.grounding.productName, "Notion")
        self.assertEqual(updated.grounding.audience, "销售团队")
        self.assertIn("Notion", updated.grounding.searchQueries)
        self.assertIn("销售团队", updated.grounding.searchQueries)
        self.assertEqual(updated.progress, 20)
        self.assertEqual(first.grounding.status, "needs_confirmation")

        db = self.SessionLocal()
        try:
            session_repo = AgentSessionRepository(db)
            message_repo = AgentMessageRepository(db)
            plan_repo = AgentPlanRepository(db)

            self.assertEqual(len(message_repo.list_for_session(session.id)), 4)
            self.assertIsNone(plan_repo.get_latest_for_session(session.id))
            session_record = session_repo.get(session.id)
            self.assertEqual(session_record.grounding_status, "needs_confirmation")
        finally:
            db.close()

        grounded = service.confirm_grounding_candidates(
            session.id,
            [candidate.id for candidate in updated.grounding.candidates[:2]],
        )
        updated_again = service.add_user_message(session.id, "再加一点品牌感")
        self.assertEqual(updated_again.status, AgentStatus.PLAN_READY)
        self.assertEqual(updated_again.grounding.status, "confirmed")
        self.assertEqual(updated_again.plan.title, grounded.plan.title)

        db = self.SessionLocal()
        try:
            message_repo = AgentMessageRepository(db)
            plan_repo = AgentPlanRepository(db)

            self.assertEqual(len(message_repo.list_for_session(session.id)), 7)
            self.assertEqual(plan_repo.get_latest_for_session(session.id).version, 3)
        finally:
            db.close()

    def test_add_user_message_after_plan_persists_revision_observation_and_updates_current_plan(self):
        from backend.db.repositories import AgentObservationRepository, AgentPlanRepository, AgentSessionRepository
        from backend.services.agent_session_service import AgentSessionService

        service = AgentSessionService(session_factory=self.SessionLocal)
        session = service.create_session("给 Notion AI 做一个 30 秒产品亮点视频")
        updated = service.add_user_message(session.id, "整体再商务一点，目标受众改成销售团队")

        self.assertEqual(updated.plan.style, "商务演示风格")

        db = self.SessionLocal()
        try:
            plan_repo = AgentPlanRepository(db)
            observation_repo = AgentObservationRepository(db)
            session_repo = AgentSessionRepository(db)

            plans = plan_repo.list_for_session(session.id)
            self.assertEqual(plans[-1].trigger_type, "user_revision")
            self.assertEqual(plans[-1].parent_plan_id, plans[-2].id)
            self.assertEqual(observation_repo.list_for_session(session.id)[-1].observation_type, "user_revision")
            self.assertEqual(session_repo.get(session.id).current_plan_id, plans[-1].id)
        finally:
            db.close()

    def test_add_user_message_rejects_non_editable_session_states(self):
        from backend.db.repositories import AgentSessionRepository
        from backend.services.agent_session_service import AgentSessionService

        db = self.SessionLocal()
        try:
            session_record = AgentSessionRepository(db).create(
                status="searching",
                current_step="正在搜索素材",
                progress=35,
            )
            blocked_session_id = session_record.id
            db.commit()
        finally:
            db.close()

        service = AgentSessionService(session_factory=self.SessionLocal)

        with self.assertRaises(RuntimeError):
            service.add_user_message(blocked_session_id, "继续改一下方案")


if __name__ == "__main__":
    unittest.main()
