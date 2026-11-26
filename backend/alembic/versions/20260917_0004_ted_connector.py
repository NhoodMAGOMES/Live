"""Add the TED connector type.

Revision ID: 20260917_0004
Revises: 20260628_0003
Create Date: 2026-09-17
"""

from alembic import op


revision = "20260917_0004"
down_revision = "20260628_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE source_connector_type ADD VALUE IF NOT EXISTS 'TED_API'")


def downgrade() -> None:
    # PostgreSQL enum values cannot be removed safely while rows may use them.
    pass
