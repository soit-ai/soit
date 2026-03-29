"""Drop MCP-specific Agent binding refs and scrub stored Agent specs.

Revision ID: 20260330143000_drop_agent_mcp_binding_refs
Revises: 20260330130000_drop_recent_runtime_foreign_keys
Create Date: 2026-03-30 14:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260330143000_drop_agent_mcp_binding_refs"
down_revision = "20260330130000_drop_recent_runtime_foreign_keys"
branch_labels = None
depends_on = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    return table_name in set(_inspector().get_table_names())


def upgrade() -> None:
    if _has_table("agent_versions"):
        op.execute(
            sa.text(
                """
                UPDATE agent_versions
                SET spec_json = jsonb_strip_nulls(
                    jsonb_set(
                        spec_json::jsonb,
                        '{bindings}',
                        (
                            COALESCE(spec_json::jsonb->'bindings', '{}'::jsonb)
                            - 'mcp_server_refs'
                            - 'mcp_tool_refs'
                            - 'mcp_resource_refs'
                        ),
                        true
                    )
                )::json
                WHERE spec_json::jsonb ? 'bindings'
                """
            )
        )

    if _has_table("agent_bindings"):
        op.execute(
            sa.text(
                """
                DELETE FROM agent_bindings
                WHERE binding_type IN ('mcp_server', 'mcp_tool', 'mcp_resource')
                """
            )
        )


def downgrade() -> None:
    return None
