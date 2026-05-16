"""add agent run trace model

Revision ID: 20260516_add_agent_run_trace_model
Revises: 20260508_add_planner_persistence_foundations
Create Date: 2026-05-16 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260516_add_agent_run_trace_model"
down_revision = "20260508_add_planner_persistence_foundations"
branch_labels = None
depends_on = None


def _set_sqlite_foreign_keys(enabled: bool) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    bind.exec_driver_sql(f"PRAGMA foreign_keys={'ON' if enabled else 'OFF'}")


def _batch_kwargs() -> dict[str, str]:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return {"recreate": "always"}
    return {}


def upgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        with op.batch_alter_table("agent_sessions", **_batch_kwargs()) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "active_operation_type",
                    sa.String(length=32),
                    nullable=False,
                    server_default="none",
                )
            )
            batch_op.add_column(sa.Column("active_operation_id", sa.String(length=36), nullable=True))

        op.create_table(
            "agent_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("source_message_id", sa.String(length=36), nullable=True),
            sa.Column("trigger_type", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("parent_run_id", sa.String(length=36), nullable=True),
            sa.Column("related_job_id", sa.String(length=36), nullable=True),
            sa.Column("actor_type", sa.String(length=32), nullable=False),
            sa.Column("actor_role", sa.String(length=64), nullable=False),
            sa.Column("actor_id", sa.String(length=128), nullable=True),
            sa.Column("agent_name", sa.String(length=128), nullable=True),
            sa.Column("input_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("output_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["parent_run_id"], ["agent_runs.id"]),
            sa.ForeignKeyConstraint(["related_job_id"], ["agent_jobs.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.ForeignKeyConstraint(["source_message_id"], ["agent_messages.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_table(
            "agent_steps",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("job_id", sa.String(length=36), nullable=True),
            sa.Column("step_key", sa.String(length=64), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("progress", sa.Float(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("result_json", sa.JSON(), nullable=True),
            sa.Column("error_json", sa.JSON(), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("actor_type", sa.String(length=32), nullable=False),
            sa.Column("actor_role", sa.String(length=64), nullable=False),
            sa.Column("actor_id", sa.String(length=128), nullable=True),
            sa.Column("agent_name", sa.String(length=128), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"]),
            sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_table(
            "agent_trace_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("run_id", sa.String(length=36), nullable=True),
            sa.Column("step_id", sa.String(length=36), nullable=True),
            sa.Column("job_id", sa.String(length=36), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("level", sa.String(length=16), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("actor_type", sa.String(length=32), nullable=False),
            sa.Column("actor_role", sa.String(length=64), nullable=False),
            sa.Column("actor_id", sa.String(length=128), nullable=True),
            sa.Column("agent_name", sa.String(length=128), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"]),
            sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.ForeignKeyConstraint(["step_id"], ["agent_steps.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

        op.create_index(
            "idx_agent_runs_session_id_created_at",
            "agent_runs",
            ["session_id", "created_at"],
        )
        op.create_index(
            "idx_agent_runs_session_id_status",
            "agent_runs",
            ["session_id", "status"],
        )
        op.create_index(
            "idx_agent_runs_parent_run_id_created_at",
            "agent_runs",
            ["parent_run_id", "created_at"],
        )
        op.create_index(
            "idx_agent_runs_related_job_id_created_at",
            "agent_runs",
            ["related_job_id", "created_at"],
        )
        op.create_index(
            "idx_agent_steps_session_id_sequence",
            "agent_steps",
            ["session_id", "sequence"],
        )
        op.create_index(
            "idx_agent_steps_run_id_sequence",
            "agent_steps",
            ["run_id", "sequence"],
        )
        op.create_index(
            "idx_agent_steps_job_id_sequence",
            "agent_steps",
            ["job_id", "sequence"],
        )
        op.create_index(
            "idx_agent_trace_events_session_id_sequence",
            "agent_trace_events",
            ["session_id", "sequence"],
        )
        op.create_index(
            "uq_agent_trace_events_session_id_sequence",
            "agent_trace_events",
            ["session_id", "sequence"],
            unique=True,
        )
        op.create_index(
            "idx_agent_trace_events_run_id_sequence",
            "agent_trace_events",
            ["run_id", "sequence"],
        )
        op.create_index(
            "idx_agent_trace_events_step_id_sequence",
            "agent_trace_events",
            ["step_id", "sequence"],
        )
        op.create_index(
            "idx_agent_trace_events_job_id_sequence",
            "agent_trace_events",
            ["job_id", "sequence"],
        )
    finally:
        _set_sqlite_foreign_keys(True)


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        op.drop_index("idx_agent_trace_events_job_id_sequence", table_name="agent_trace_events")
        op.drop_index("idx_agent_trace_events_step_id_sequence", table_name="agent_trace_events")
        op.drop_index("idx_agent_trace_events_run_id_sequence", table_name="agent_trace_events")
        op.drop_index("uq_agent_trace_events_session_id_sequence", table_name="agent_trace_events")
        op.drop_index("idx_agent_trace_events_session_id_sequence", table_name="agent_trace_events")
        op.drop_index("idx_agent_steps_job_id_sequence", table_name="agent_steps")
        op.drop_index("idx_agent_steps_run_id_sequence", table_name="agent_steps")
        op.drop_index("idx_agent_steps_session_id_sequence", table_name="agent_steps")
        op.drop_index("idx_agent_runs_related_job_id_created_at", table_name="agent_runs")
        op.drop_index("idx_agent_runs_parent_run_id_created_at", table_name="agent_runs")
        op.drop_index("idx_agent_runs_session_id_status", table_name="agent_runs")
        op.drop_index("idx_agent_runs_session_id_created_at", table_name="agent_runs")
        op.drop_table("agent_trace_events")
        op.drop_table("agent_steps")
        op.drop_table("agent_runs")

        with op.batch_alter_table("agent_sessions", **_batch_kwargs()) as batch_op:
            batch_op.drop_column("active_operation_id")
            batch_op.drop_column("active_operation_type")
    finally:
        _set_sqlite_foreign_keys(True)
