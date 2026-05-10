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
