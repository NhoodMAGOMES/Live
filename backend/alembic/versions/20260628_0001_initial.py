"""Initial LIVE Pulse schema.

Revision ID: 20260628_0001
Revises:
Create Date: 2026-06-28
"""

from alembic import op

from app import models  # noqa: F401
from app.db.session import Base


revision = "20260628_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
    op.execute("DROP EXTENSION IF EXISTS vector")

