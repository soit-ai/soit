"""Collapse the non-admin tenant roles into Member.

Tenant roles used the workspace ladder (Owner/Admin/Dev/Viewer), but only
Owner and Admin ever meant anything at the tenant level: Dev and Viewer
granted nothing there and served only to seed a workspace role at sign-in.
The organization now has Owner, Admin and Member; what a member may do in a
workspace is their workspace role alone.

Revision ID: 20261126120000
Revises: 20261126110000
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20261126120000"
down_revision: str | Sequence[str] | None = "20261126110000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE tenant_memberships SET role = 'Member' WHERE role NOT IN ('Owner', 'Admin')")


def downgrade() -> None:
    # Dev and Viewer were indistinguishable at the tenant level; Viewer is the
    # one that grants the least if anything ever reads it again.
    op.execute("UPDATE tenant_memberships SET role = 'Viewer' WHERE role = 'Member'")
