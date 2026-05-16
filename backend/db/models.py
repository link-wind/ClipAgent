from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


def _new_uuid() -> str:
    # 生成字符串主键
    return str(uuid4())


class AgentSessionRecord(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(128), nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_retryable_step: Mapped[str | None] = mapped_column(String(128), nullable=True)
    active_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id"),
        nullable=True,
    )
    active_operation_type: Mapped[str] = mapped_column(String(32), default="none", nullable=False)
    active_operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_plans.id"),
        nullable=True,
    )
    planner_trace_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    grounding_status: Mapped[str | None] = mapped_column(
        String(32),
        default="pending_search",
        nullable=True,
    )
    grounding_summary_json: Mapped[dict | None] = mapped_column(
        JSON,
        default=dict,
        nullable=True,
    )
    selected_candidate_ids_json: Mapped[list | None] = mapped_column(
        JSON,
        default=list,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class AgentMessageRecord(Base):
    __tablename__ = "agent_messages"
    __table_args__ = (
        Index("idx_agent_messages_session_id_created_at", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentRunRecord(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("idx_agent_runs_session_id_created_at", "session_id", "created_at"),
        Index("idx_agent_runs_session_id_status", "session_id", "status"),
        Index("idx_agent_runs_parent_run_id_created_at", "parent_run_id", "created_at"),
        Index("idx_agent_runs_related_job_id_created_at", "related_job_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=False,
    )
    source_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_messages.id"),
        nullable=True,
    )
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id"),
        nullable=True,
    )
    related_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id"),
        nullable=True,
    )
    actor_type: Mapped[str] = mapped_column(String(32), default="agent", nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), default="planner", nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(128), default="clipforge_agent", nullable=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class AgentStepRecord(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        Index("idx_agent_steps_session_id_sequence", "session_id", "sequence"),
        Index("idx_agent_steps_run_id_sequence", "run_id", "sequence"),
        Index("idx_agent_steps_job_id_sequence", "job_id", "sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=False,
    )
    run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id"),
        nullable=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id"),
        nullable=True,
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default="agent", nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), default="planner", nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(128), default="clipforge_agent", nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class AgentTraceEventRecord(Base):
    __tablename__ = "agent_trace_events"
    __table_args__ = (
        Index("idx_agent_trace_events_session_id_sequence", "session_id", "sequence"),
        Index("idx_agent_trace_events_run_id_sequence", "run_id", "sequence"),
        Index("idx_agent_trace_events_step_id_sequence", "step_id", "sequence"),
        Index("idx_agent_trace_events_job_id_sequence", "job_id", "sequence"),
        Index("uq_agent_trace_events_session_id_sequence", "session_id", "sequence", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=False,
    )
    run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id"),
        nullable=True,
    )
    step_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_steps.id"),
        nullable=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    level: Mapped[str] = mapped_column(String(16), default="info", nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    actor_type: Mapped[str] = mapped_column(String(32), default="agent", nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), default="planner", nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(128), default="clipforge_agent", nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentPlanRecord(Base):
    __tablename__ = "agent_plans"
    __table_args__ = (
        Index("idx_agent_plans_session_id_version", "session_id", "version", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    style: Mapped[str | None] = mapped_column(String(128), nullable=True)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    parent_plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_plans.id"),
        nullable=True,
    )
    trigger_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    planner_mode: Mapped[str | None] = mapped_column(String(32), nullable=True)
    planner_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    execution_plan_json: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentObservationRecord(Base):
    __tablename__ = "agent_observations"
    __table_args__ = (
        Index("idx_agent_observations_session_id_created_at", "session_id", "created_at"),
        Index("idx_agent_observations_plan_id_created_at", "plan_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=False,
    )
    plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_plans.id"),
        nullable=True,
    )
    observation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_messages.id"),
        nullable=True,
    )
    source_job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentJobRecord(Base):
    __tablename__ = "agent_jobs"
    __table_args__ = (
        Index("idx_agent_jobs_session_id_created_at", "session_id", "created_at"),
        Index("idx_agent_jobs_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=True,
    )
    plan_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_plans.id"),
        nullable=True,
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    worker_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class AgentEventRecord(Base):
    __tablename__ = "agent_events"
    __table_args__ = (
        Index("idx_agent_events_session_id_created_at", "session_id", "created_at"),
        Index("idx_agent_events_job_id_created_at", "job_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    step: Mapped[str | None] = mapped_column(String(128), nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentArtifactRecord(Base):
    __tablename__ = "agent_artifacts"
    __table_args__ = (
        Index("idx_agent_artifacts_session_id_created_at", "session_id", "created_at"),
        Index("idx_agent_artifacts_job_id_artifact_type", "job_id", "artifact_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=True,
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_jobs.id"),
        nullable=True,
    )
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    scene_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    public_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class KnowledgeSourceRecord(Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        Index("idx_knowledge_sources_project_key_created_at", "project_key", "created_at"),
        Index("idx_knowledge_sources_status_updated_at", "status", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    project_key: Mapped[str] = mapped_column(String(128), default="default", nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    active_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    processing_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_failed_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class KnowledgeVersionRecord(Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (
        Index("idx_knowledge_versions_source_id_created_at", "source_id", "created_at"),
        Index("uq_knowledge_versions_source_id_version_number", "source_id", "version_number", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_sources.id"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class KnowledgeChunkRecord(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("idx_knowledge_chunks_source_id_created_at", "source_id", "created_at"),
        Index("idx_knowledge_chunks_version_id_index", "version_id", "chunk_index"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_sources.id"),
        nullable=False,
    )
    version_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_versions.id"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_type: Mapped[str] = mapped_column(String(64), default="text", nullable=False)
    title_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentContextUsageRecord(Base):
    __tablename__ = "agent_context_usages"
    __table_args__ = (
        Index("idx_agent_context_usages_session_id_created_at", "session_id", "created_at"),
        Index("idx_agent_context_usages_run_id_created_at", "run_id", "created_at"),
        Index("idx_agent_context_usages_chunk_id_created_at", "chunk_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_sessions.id"),
        nullable=False,
    )
    run_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id"),
        nullable=True,
    )
    source: Mapped[str] = mapped_column(String(64), default="knowledge", nullable=False)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_chunks.id"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    usage_type: Mapped[str] = mapped_column(String(64), default="planning_context", nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ToolCallRecord(Base):
    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("idx_tool_calls_run_id_started_at", "run_id", "started_at"),
        Index("idx_tool_calls_step_id_started_at", "step_id", "started_at"),
        Index("idx_tool_calls_tool_id_started_at", "tool_id", "started_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    tool_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="started", nullable=False)
    arguments_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    result_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    result_ref: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actor: Mapped[str] = mapped_column(String(128), default="agent_runtime", nullable=False)
    actor_role: Mapped[str] = mapped_column(String(64), default="planner", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
