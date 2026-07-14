"""add provider model split configuration json

Revision ID: 20260608110000_provider_model_configuration_json
Revises: 20260608100000_provider_configuration_json
Create Date: 2026-06-08 11:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260608110000_provider_model_configuration_json"
down_revision = "20260608100000_provider_configuration_json"
branch_labels = None
depends_on = None


def _columns(conn, table_name: str) -> set[str]:
    if table_name not in sa.inspect(conn).get_table_names():
        return set()
    return {column["name"] for column in sa.inspect(conn).get_columns(table_name)}


def upgrade() -> None:
    conn = op.get_bind()
    if "provider_models" not in sa.inspect(conn).get_table_names():
        return

    columns = _columns(conn, "provider_models")
    for column_name in (
        "architecture_json",
        "capability_matrix_json",
        "parameter_config_json",
        "pricing_json",
        "diagnostics_json",
    ):
        if column_name not in columns:
            op.add_column("provider_models", sa.Column(column_name, sa.JSON(), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if "provider_models" not in sa.inspect(conn).get_table_names():
        return

    columns = _columns(conn, "provider_models")
    for column_name in (
        "diagnostics_json",
        "pricing_json",
        "parameter_config_json",
        "capability_matrix_json",
        "architecture_json",
    ):
        if column_name in columns:
            op.drop_column("provider_models", column_name)
