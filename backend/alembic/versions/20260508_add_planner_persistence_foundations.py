"""add planner persistence foundations

Revision ID: 20260508_add_planner_persistence_foundations
Revises: 20260507_add_agent_grounding_state
Create Date: 2026-05-08 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260508_add_planner_persistence_foundations"
down_revision = "20260507_add_agent_grounding_state"
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
        op.execute(
            """
            WITH ranked_plans AS (
                SELECT
                    id,
                    session_id,
                    version,
                    created_at,
                    ROW_NUMBER() OVER (
                        PARTITION BY session_id, version
                        ORDER BY created_at ASC, id ASC
                    ) AS duplicate_rank
                FROM agent_plans
            ),
            session_max_versions AS (
                SELECT
                    session_id,
                    MAX(version) AS max_version
                FROM agent_plans
                GROUP BY session_id
            ),
            duplicate_offsets AS (
                SELECT
                    ranked_plans.id,
                    session_max_versions.max_version
                    + ROW_NUMBER() OVER (
                        PARTITION BY ranked_plans.session_id
                        ORDER BY ranked_plans.version ASC, ranked_plans.created_at ASC, ranked_plans.id ASC
                    ) AS normalized_version
                FROM ranked_plans
                JOIN session_max_versions
                    ON session_max_versions.session_id = ranked_plans.session_id
                WHERE duplicate_rank > 1
            )
            UPDATE agent_plans
            SET version = (
                SELECT normalized_version
                FROM duplicate_offsets
                WHERE duplicate_offsets.id = agent_plans.id
            )
            WHERE id IN (SELECT id FROM duplicate_offsets)
            """
        )

        with op.batch_alter_table("agent_sessions", **_batch_kwargs()) as batch_op:
            batch_op.add_column(sa.Column("current_plan_id", sa.String(length=36), nullable=True))
            batch_op.add_column(
                sa.Column(
                    "planner_trace_json",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'{}'"),
                )
            )
            batch_op.create_foreign_key(
                "fk_agent_sessions_current_plan_id",
                "agent_plans",
                ["current_plan_id"],
                ["id"],
            )

        with op.batch_alter_table("agent_plans", **_batch_kwargs()) as batch_op:
            batch_op.add_column(sa.Column("parent_plan_id", sa.String(length=36), nullable=True))
            batch_op.add_column(sa.Column("trigger_type", sa.String(length=64), nullable=True))
            batch_op.add_column(sa.Column("planner_mode", sa.String(length=32), nullable=True))
            batch_op.add_column(sa.Column("planner_model", sa.String(length=128), nullable=True))
            batch_op.add_column(
                sa.Column(
                    "execution_plan_json",
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'{}'"),
                )
            )
            batch_op.add_column(sa.Column("change_summary", sa.Text(), nullable=True))
            batch_op.add_column(
                sa.Column("status", sa.String(length=32), nullable=False, server_default="draft")
            )
            batch_op.create_foreign_key(
                "fk_agent_plans_parent_plan_id",
                "agent_plans",
                ["parent_plan_id"],
                ["id"],
            )
            batch_op.drop_index("idx_agent_plans_session_id_version")
            batch_op.create_index(
                "idx_agent_plans_session_id_version",
                ["session_id", "version"],
                unique=True,
            )

        op.create_table(
            "agent_observations",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("plan_id", sa.String(length=36), nullable=True),
            sa.Column("observation_type", sa.String(length=64), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("source_message_id", sa.String(length=36), nullable=True),
            sa.Column("source_job_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"]),
            sa.ForeignKeyConstraint(["plan_id"], ["agent_plans.id"]),
            sa.ForeignKeyConstraint(["source_job_id"], ["agent_jobs.id"]),
            sa.ForeignKeyConstraint(["source_message_id"], ["agent_messages.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_agent_observations_session_id_created_at",
            "agent_observations",
            ["session_id", "created_at"],
        )
        op.create_index(
            "idx_agent_observations_plan_id_created_at",
            "agent_observations",
            ["plan_id", "created_at"],
        )
    finally:
        _set_sqlite_foreign_keys(True)


def downgrade() -> None:
    _set_sqlite_foreign_keys(False)
    try:
        op.drop_index("idx_agent_observations_plan_id_created_at", table_name="agent_observations")
        op.drop_index("idx_agent_observations_session_id_created_at", table_name="agent_observations")
        op.drop_table("agent_observations")

        with op.batch_alter_table("agent_plans", **_batch_kwargs()) as batch_op:
            batch_op.drop_constraint("fk_agent_plans_parent_plan_id", type_="foreignkey")
            batch_op.drop_index("idx_agent_plans_session_id_version")
            batch_op.create_index("idx_agent_plans_session_id_version", ["session_id", "version"])
            batch_op.drop_column("status")
            batch_op.drop_column("change_summary")
            batch_op.drop_column("execution_plan_json")
            batch_op.drop_column("planner_model")
            batch_op.drop_column("planner_mode")
            batch_op.drop_column("trigger_type")
            batch_op.drop_column("parent_plan_id")

        with op.batch_alter_table("agent_sessions", **_batch_kwargs()) as batch_op:
            batch_op.drop_constraint("fk_agent_sessions_current_plan_id", type_="foreignkey")
            batch_op.drop_column("planner_trace_json")
            batch_op.drop_column("current_plan_id")
    finally:
        _set_sqlite_foreign_keys(True)
