"""create agent tables

Revision ID: 20260502_create_agent_tables
Revises:
Create Date: 2026-05-02 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260502_create_agent_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step", sa.String(length=128), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("video_url", sa.String(length=512), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_retryable_step", sa.String(length=128), nullable=True),
        sa.Column("active_job_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("target_duration", sa.Integer(), nullable=True),
        sa.Column("style", sa.String(length=128), nullable=True),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("plan_id", sa.String(length=36), nullable=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("current_step", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("worker_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["agent_plans.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("step", sa.String(length=128), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("scene_id", sa.String(length=36), nullable=True),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("local_path", sa.String(length=512), nullable=True),
        sa.Column("public_url", sa.String(length=512), nullable=True),
        sa.Column("duration", sa.Float(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_foreign_key(
        "fk_agent_sessions_active_job_id",
        "agent_sessions",
        "agent_jobs",
        ["active_job_id"],
        ["id"],
    )

    op.create_index(
        "idx_agent_messages_session_id_created_at",
        "agent_messages",
        ["session_id", "created_at"],
    )
    op.create_index(
        "idx_agent_plans_session_id_version",
        "agent_plans",
        ["session_id", "version"],
    )
    op.create_index(
        "idx_agent_jobs_session_id_created_at",
        "agent_jobs",
        ["session_id", "created_at"],
    )
    op.create_index(
        "idx_agent_jobs_status_created_at",
        "agent_jobs",
        ["status", "created_at"],
    )
    op.create_index(
        "idx_agent_events_session_id_created_at",
        "agent_events",
        ["session_id", "created_at"],
    )
    op.create_index(
        "idx_agent_events_job_id_created_at",
        "agent_events",
        ["job_id", "created_at"],
    )
    op.create_index(
        "idx_agent_artifacts_session_id_created_at",
        "agent_artifacts",
        ["session_id", "created_at"],
    )
    op.create_index(
        "idx_agent_artifacts_job_id_artifact_type",
        "agent_artifacts",
        ["job_id", "artifact_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_agent_artifacts_job_id_artifact_type", table_name="agent_artifacts")
    op.drop_index("idx_agent_artifacts_session_id_created_at", table_name="agent_artifacts")
    op.drop_index("idx_agent_events_job_id_created_at", table_name="agent_events")
    op.drop_index("idx_agent_events_session_id_created_at", table_name="agent_events")
    op.drop_index("idx_agent_jobs_status_created_at", table_name="agent_jobs")
    op.drop_index("idx_agent_jobs_session_id_created_at", table_name="agent_jobs")
    op.drop_index("idx_agent_plans_session_id_version", table_name="agent_plans")
    op.drop_index("idx_agent_messages_session_id_created_at", table_name="agent_messages")
    op.drop_constraint("fk_agent_sessions_active_job_id", "agent_sessions", type_="foreignkey")
    op.drop_table("agent_artifacts")
    op.drop_table("agent_events")
    op.drop_table("agent_jobs")
    op.drop_table("agent_plans")
    op.drop_table("agent_messages")
    op.drop_table("agent_sessions")
