"""add knowledge management phase2_2

Revision ID: 20260517_add_knowledge_management_phase2_2
Revises: 20260516_add_rag_foundation
Create Date: 2026-05-17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260517_add_knowledge_management_phase2_2"
down_revision = "20260516_add_rag_foundation"
branch_labels = None
depends_on = None


def _set_sqlite_foreign_keys(enabled: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    bind.exec_driver_sql(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def upgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        op.drop_index("idx_agent_context_usages_chunk_id_created_at", table_name="agent_context_usages")
        op.drop_index("idx_agent_context_usages_run_id_created_at", table_name="agent_context_usages")
        op.drop_index("idx_agent_context_usages_session_id_created_at", table_name="agent_context_usages")
        op.drop_table("agent_context_usages")

        op.drop_index("idx_knowledge_chunks_document_id_index", table_name="knowledge_chunks")
        op.drop_table("knowledge_chunks")

        op.drop_index("idx_knowledge_documents_source_id_created_at", table_name="knowledge_documents")
        op.drop_table("knowledge_documents")

        op.drop_index("idx_knowledge_sources_source_type_created_at", table_name="knowledge_sources")
        op.drop_table("knowledge_sources")

        op.create_table(
            "knowledge_sources",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_key", sa.String(length=128), nullable=False, server_default="default"),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("active_version_id", sa.String(length=36), nullable=True),
            sa.Column("processing_version_id", sa.String(length=36), nullable=True),
            sa.Column("last_failed_version_id", sa.String(length=36), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("deletion_requested_at", sa.DateTime(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_knowledge_sources_project_key_created_at",
            "knowledge_sources",
            ["project_key", "created_at"],
        )
        op.create_index(
            "idx_knowledge_sources_status_updated_at",
            "knowledge_sources",
            ["status", "updated_at"],
        )

        op.create_table(
            "knowledge_versions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source_id", sa.String(length=36), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
            sa.Column("content_hash", sa.String(length=128), nullable=False),
            sa.Column("storage_path", sa.String(length=512), nullable=True),
            sa.Column("original_filename", sa.String(length=255), nullable=True),
            sa.Column("file_size", sa.Integer(), nullable=True),
            sa.Column("parser_type", sa.String(length=64), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.Column("failed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_knowledge_versions_source_id_created_at",
            "knowledge_versions",
            ["source_id", "created_at"],
        )
        op.create_index(
            "uq_knowledge_versions_source_id_version_number",
            "knowledge_versions",
            ["source_id", "version_number"],
            unique=True,
        )

        op.create_table(
            "knowledge_chunks",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source_id", sa.String(length=36), nullable=False),
            sa.Column("version_id", sa.String(length=36), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("chunk_type", sa.String(length=64), nullable=False, server_default="text"),
            sa.Column("title_path", sa.String(length=512), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
            sa.ForeignKeyConstraint(["version_id"], ["knowledge_versions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_knowledge_chunks_source_id_created_at",
            "knowledge_chunks",
            ["source_id", "created_at"],
        )
        op.create_index(
            "idx_knowledge_chunks_version_id_index",
            "knowledge_chunks",
            ["version_id", "chunk_index"],
        )

        op.create_table(
            "agent_context_usages",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("query_text", sa.Text(), nullable=False),
            sa.Column("chunk_id", sa.String(length=36), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("usage_type", sa.String(length=64), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunks.id"]),
            sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_agent_context_usages_session_id_created_at",
            "agent_context_usages",
            ["session_id", "created_at"],
        )
        op.create_index(
            "idx_agent_context_usages_run_id_created_at",
            "agent_context_usages",
            ["run_id", "created_at"],
        )
        op.create_index(
            "idx_agent_context_usages_chunk_id_created_at",
            "agent_context_usages",
            ["chunk_id", "created_at"],
        )
    finally:
        _set_sqlite_foreign_keys(True)


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        op.drop_index("idx_agent_context_usages_chunk_id_created_at", table_name="agent_context_usages")
        op.drop_index("idx_agent_context_usages_run_id_created_at", table_name="agent_context_usages")
        op.drop_index("idx_agent_context_usages_session_id_created_at", table_name="agent_context_usages")
        op.drop_table("agent_context_usages")

        op.drop_index("idx_knowledge_chunks_version_id_index", table_name="knowledge_chunks")
        op.drop_index("idx_knowledge_chunks_source_id_created_at", table_name="knowledge_chunks")
        op.drop_table("knowledge_chunks")

        op.drop_index("uq_knowledge_versions_source_id_version_number", table_name="knowledge_versions")
        op.drop_index("idx_knowledge_versions_source_id_created_at", table_name="knowledge_versions")
        op.drop_table("knowledge_versions")

        op.drop_index("idx_knowledge_sources_status_updated_at", table_name="knowledge_sources")
        op.drop_index("idx_knowledge_sources_project_key_created_at", table_name="knowledge_sources")
        op.drop_table("knowledge_sources")

        op.create_table(
            "knowledge_sources",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source_type", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("uri", sa.String(length=512), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_knowledge_sources_source_type_created_at",
            "knowledge_sources",
            ["source_type", "created_at"],
        )

        op.create_table(
            "knowledge_documents",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("source_id", sa.String(length=36), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_knowledge_documents_source_id_created_at",
            "knowledge_documents",
            ["source_id", "created_at"],
        )

        op.create_table(
            "knowledge_chunks",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("document_id", sa.String(length=36), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("token_count", sa.Integer(), nullable=False),
            sa.Column("embedding_ref", sa.String(length=255), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_knowledge_chunks_document_id_index",
            "knowledge_chunks",
            ["document_id", "chunk_index"],
        )

        op.create_table(
            "agent_context_usages",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("source", sa.String(length=64), nullable=False),
            sa.Column("query_text", sa.Text(), nullable=False),
            sa.Column("chunk_id", sa.String(length=36), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("usage_type", sa.String(length=64), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["chunk_id"], ["knowledge_chunks.id"]),
            sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_agent_context_usages_session_id_created_at",
            "agent_context_usages",
            ["session_id", "created_at"],
        )
        op.create_index(
            "idx_agent_context_usages_run_id_created_at",
            "agent_context_usages",
            ["run_id", "created_at"],
        )
        op.create_index(
            "idx_agent_context_usages_chunk_id_created_at",
            "agent_context_usages",
            ["chunk_id", "created_at"],
        )
    finally:
        _set_sqlite_foreign_keys(True)
