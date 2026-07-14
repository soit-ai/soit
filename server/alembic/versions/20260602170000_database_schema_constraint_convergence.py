"""database schema convergence for foreign key constraints

Revision ID: 20260602170000_database_schema_constraint_convergence
Revises: 20260602160000_plugin_fk_constraint_convergence
Create Date: 2026-06-02 17:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260602170000_database_schema_constraint_convergence"
down_revision = "20260602160000_plugin_fk_constraint_convergence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    for table_name in sorted(inspector.get_table_names()):
        for fk in inspector.get_foreign_keys(table_name):
            fk_name = fk.get("name")
            if fk_name:
                op.drop_constraint(fk_name, table_name, type_="foreignkey")


def downgrade() -> None:
    raise NotImplementedError(
        "Database foreign key constraints are intentionally unsupported; enforce relationships in business code."
    )
