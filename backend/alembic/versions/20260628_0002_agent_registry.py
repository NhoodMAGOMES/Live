"""Add agent registry and run metrics.

Revision ID: 20260628_0002
Revises: 20260628_0001
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260628_0002"
down_revision = "20260628_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE agent_run_status AS ENUM ('RUNNING', 'SUCCESS', 'FAILED', 'SKIPPED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    agent_run_status = postgresql.ENUM("RUNNING", "SUCCESS", "FAILED", "SKIPPED", name="agent_run_status", create_type=False)

    existing_indexes = {index["name"] for index in inspector.get_indexes("agents")} if inspector.has_table("agents") else set()
    if not inspector.has_table("agents"):
        op.create_table(
            "agents",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("slug", sa.String(length=120), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("task", sa.Text(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("config", sa.JSON(), nullable=False),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
    if "ix_agents_slug" not in existing_indexes:
        op.create_index(op.f("ix_agents_slug"), "agents", ["slug"], unique=True)
    if "ix_agents_is_active" not in existing_indexes:
        op.create_index(op.f("ix_agents_is_active"), "agents", ["is_active"], unique=False)

    existing_indexes = {index["name"] for index in inspector.get_indexes("agent_runs")} if inspector.has_table("agent_runs") else set()
    if not inspector.has_table("agent_runs"):
        op.create_table(
            "agent_runs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("agent_id", sa.Integer(), nullable=False),
            sa.Column("status", agent_run_status, nullable=False),
            sa.Column("task_name", sa.String(length=255), nullable=False),
            sa.Column("target_type", sa.String(length=120), nullable=True),
            sa.Column("target_id", sa.String(length=120), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("input_count", sa.Integer(), nullable=False),
            sa.Column("output_count", sa.Integer(), nullable=False),
            sa.Column("success_count", sa.Integer(), nullable=False),
            sa.Column("failure_count", sa.Integer(), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=False),
            sa.Column("output_tokens", sa.Integer(), nullable=False),
            sa.Column("total_tokens", sa.Integer(), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("logs", sa.JSON(), nullable=False),
            sa.Column("metadata_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_agent_runs_agent_id" not in existing_indexes:
        op.create_index(op.f("ix_agent_runs_agent_id"), "agent_runs", ["agent_id"], unique=False)
    if "ix_agent_runs_target_type" not in existing_indexes:
        op.create_index(op.f("ix_agent_runs_target_type"), "agent_runs", ["target_type"], unique=False)
    if "ix_agent_runs_target_id" not in existing_indexes:
        op.create_index(op.f("ix_agent_runs_target_id"), "agent_runs", ["target_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_runs_target_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_target_type"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index(op.f("ix_agents_is_active"), table_name="agents")
    op.drop_index(op.f("ix_agents_slug"), table_name="agents")
    op.drop_table("agents")
    sa.Enum(name="agent_run_status").drop(op.get_bind(), checkfirst=True)
