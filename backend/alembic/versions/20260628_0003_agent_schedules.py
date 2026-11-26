"""Add agent scheduling fields.

Revision ID: 20260628_0003
Revises: 20260628_0002
Create Date: 2026-06-28
"""

from alembic import op
import sqlalchemy as sa


revision = "20260628_0003"
down_revision = "20260628_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("agents")}
    indexes = {index["name"] for index in inspector.get_indexes("agents")}

    if "schedule_enabled" not in columns:
        op.add_column("agents", sa.Column("schedule_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "schedule_frequency" not in columns:
        op.add_column("agents", sa.Column("schedule_frequency", sa.String(length=40), nullable=False, server_default="manual"))
    if "schedule_interval" not in columns:
        op.add_column("agents", sa.Column("schedule_interval", sa.Integer(), nullable=False, server_default="1"))
    if "schedule_time" not in columns:
        op.add_column("agents", sa.Column("schedule_time", sa.String(length=5), nullable=False, server_default="08:00"))
    if "schedule_weekday" not in columns:
        op.add_column("agents", sa.Column("schedule_weekday", sa.Integer(), nullable=False, server_default="0"))
    if "next_run_at" not in columns:
        op.add_column("agents", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
    if "ix_agents_schedule_enabled" not in indexes:
        op.create_index(op.f("ix_agents_schedule_enabled"), "agents", ["schedule_enabled"], unique=False)
    if "ix_agents_next_run_at" not in indexes:
        op.create_index(op.f("ix_agents_next_run_at"), "agents", ["next_run_at"], unique=False)
    op.execute(
        """
        UPDATE agents
        SET schedule_enabled = true,
            schedule_frequency = 'daily',
            schedule_interval = 1,
            schedule_time = '08:00',
            schedule_weekday = 0
        WHERE slug = 'verification_cycle'
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agents_next_run_at"), table_name="agents")
    op.drop_index(op.f("ix_agents_schedule_enabled"), table_name="agents")
    op.drop_column("agents", "next_run_at")
    op.drop_column("agents", "schedule_weekday")
    op.drop_column("agents", "schedule_time")
    op.drop_column("agents", "schedule_interval")
    op.drop_column("agents", "schedule_frequency")
    op.drop_column("agents", "schedule_enabled")
