"""Add verified_internal status

Revision ID: 002
Revises: 001
Create Date: 2026-05-08 00:00:00.000000
"""
from alembic import op

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL supports ADD VALUE IF NOT EXISTS so this is idempotent
    op.execute("ALTER TYPE validationstatus ADD VALUE IF NOT EXISTS 'verified_internal'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the type.
    # A full downgrade is intentionally omitted; the extra value is harmless.
    pass
