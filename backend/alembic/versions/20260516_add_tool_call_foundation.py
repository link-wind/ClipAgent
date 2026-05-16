"""add tool call foundation

Revision ID: 20260516_add_tool_call_foundation
Revises: 20260516_add_rag_foundation
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20260516_add_tool_call_foundation"
down_revision = "20260516_add_rag_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("tool_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("arguments_json", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=False),
        sa.Column("result_ref", sa.String(length=255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tool_calls_run_id_started_at", "tool_calls", ["run_id", "started_at"])
    op.create_index("idx_tool_calls_step_id_started_at", "tool_calls", ["step_id", "started_at"])
    op.create_index("idx_tool_calls_tool_id_started_at", "tool_calls", ["tool_id", "started_at"])


def downgrade() -> None:
    op.drop_index("idx_tool_calls_tool_id_started_at", table_name="tool_calls")
    op.drop_index("idx_tool_calls_step_id_started_at", table_name="tool_calls")
    op.drop_index("idx_tool_calls_run_id_started_at", table_name="tool_calls")
    op.drop_table("tool_calls")
