"""add agent grounding state

Revision ID: 20260507_add_agent_grounding_state
Revises: 20260502_create_agent_tables
Create Date: 2026-05-07 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260507_add_agent_grounding_state"
down_revision = "20260502_create_agent_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agent_sessions",
        sa.Column("grounding_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "agent_sessions",
        sa.Column("grounding_summary_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "agent_sessions",
        sa.Column("selected_candidate_ids_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_sessions", "selected_candidate_ids_json")
    op.drop_column("agent_sessions", "grounding_summary_json")
    op.drop_column("agent_sessions", "grounding_status")
