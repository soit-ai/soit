"""drop run app foreign keys

Revision ID: 20260307143000_drop_run_app_foreign_keys
Revises: 20260307123000_run_subject_fields
Create Date: 2026-03-07 14:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260307143000_drop_run_app_foreign_keys"
down_revision = "20260307123000_run_subject_fields"
branch_labels = None
depends_on = None


def _drop_run_foreign_keys() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    foreign_keys = inspector.get_foreign_keys("runs")
    target_names = {
        fk["name"]
        for fk in foreign_keys
        if fk.get("referred_table") in {"apps", "app_versions"}
    }
    if not target_names:
        return

    with op.batch_alter_table("runs") as batch_op:
        for constraint_name in sorted(target_names):
            batch_op.drop_constraint(constraint_name, type_="foreignkey")


def upgrade() -> None:
    _drop_run_foreign_keys()


def downgrade() -> None:
    # The AppCenter tables have been retired, so these foreign keys are not restored.
    return None
