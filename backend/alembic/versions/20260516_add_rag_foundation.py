"""add rag foundation

Revision ID: 20260516_add_rag_foundation
Revises: 20260516_add_agent_run_trace_model
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260516_add_rag_foundation"
down_revision = "20260516_add_agent_run_trace_model"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("uri", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_knowledge_sources_source_type_created_at", "knowledge_sources", ["source_type", "created_at"])

    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("knowledge_sources.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_knowledge_documents_source_id_created_at", "knowledge_documents", ["source_id", "created_at"])

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("document_id", sa.String(length=36), sa.ForeignKey("knowledge_documents.id"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding_ref", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_knowledge_chunks_document_id_index", "knowledge_chunks", ["document_id", "chunk_index"])

    op.create_table(
        "agent_context_usages",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("agent_sessions.id"), nullable=False),
        sa.Column("run_id", sa.String(length=36), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("chunk_id", sa.String(length=36), sa.ForeignKey("knowledge_chunks.id"), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("usage_type", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_agent_context_usages_session_id_created_at", "agent_context_usages", ["session_id", "created_at"])
    op.create_index("idx_agent_context_usages_run_id_created_at", "agent_context_usages", ["run_id", "created_at"])
    op.create_index("idx_agent_context_usages_chunk_id_created_at", "agent_context_usages", ["chunk_id", "created_at"])


def downgrade() -> None:
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
