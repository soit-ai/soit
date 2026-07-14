"""drop legacy skill/mcp tables after plugin artifact convergence

Revision ID: 20260602150000_legacy_skill_mcp_table_cleanup
Revises: 20260602140000_plugin_artifact_skill_mcp_convergence
Create Date: 2026-06-02 15:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260602150000_legacy_skill_mcp_table_cleanup"
down_revision = "20260602140000_plugin_artifact_skill_mcp_convergence"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _tables()
    for table_name in ("skill_publishes", "skill_versions", "mcp_servers", "skills"):
        if table_name in tables:
            op.drop_table(table_name)


def downgrade() -> None:
    raise NotImplementedError(
        "Legacy skill/mcp table cleanup is irreversible; plugin artifacts are the only supported model."
    )
