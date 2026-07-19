"""Create the complete SOIT schema for a fresh installation.

Revision ID: 20260718140000
Revises:
Create Date: 2026-07-18 14:00:00
"""

from __future__ import annotations

from alembic import op
from sqlmodel import SQLModel

import app.kernel.runtime.db.models  # noqa: F401
import app.modules  # noqa: F401
from app.modules.modelhub.domain import models as modelhub_models  # noqa: F401


revision = "20260718140000"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables described by the current application metadata."""

    SQLModel.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    """Drop the fresh-install schema."""

    SQLModel.metadata.drop_all(bind=op.get_bind())
