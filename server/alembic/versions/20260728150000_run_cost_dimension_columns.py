"""Add dimension columns to run_cost_entries and merge latency rows.

Each metered invocation becomes one row: dedicated columns carry the
measured dimensions (latency_ms, request_count, embedding_count,
rerank_count, vector_count, storage_bytes) so aggregations never depend
on the generic unit/quantity pair. Historical per-step ``ms`` rows are
merged into their sibling usage row; orphan ``ms`` rows survive as
observation rows with latency_ms backfilled.

Revision ID: 20260728150000
Revises: 20260728120000
Create Date: 2026-07-28 15:00:00
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260728150000"
down_revision: Union[str, Sequence[str], None] = "20260728120000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DIMENSION_COLUMNS = (
    "latency_ms",
    "request_count",
    "embedding_count",
    "rerank_count",
    "vector_count",
    "storage_bytes",
)

_SOURCE_PORT_BY_UNIT = {
    "tokens": "llm",
    "embeddings": "llm",
    "embedding": "llm",
    "rerank": "llm",
    "ms": "llm",
    "vectors": "vector",
    "bytes": "storage",
}

_SOURCE_PORT_BY_PROVIDER = {
    "vector": "vector",
    "storage": "storage",
    "plugin": "plugins",
}


def _cost_entries_table() -> sa.Table:
    return sa.table(
        "run_cost_entries",
        sa.column("id", sa.String()),
        sa.column("run_id", sa.String()),
        sa.column("step_id", sa.String()),
        sa.column("entry_type", sa.String()),
        sa.column("unit", sa.String()),
        sa.column("quantity", sa.Numeric(18, 6)),
        sa.column("provider", sa.String()),
        sa.column("source_port", sa.String()),
        sa.column("operation", sa.String()),
        sa.column("latency_ms", sa.Integer()),
        sa.column("request_count", sa.Integer()),
        sa.column("embedding_count", sa.Integer()),
        sa.column("rerank_count", sa.Integer()),
        sa.column("vector_count", sa.Integer()),
        sa.column("storage_bytes", sa.BigInteger()),
    )


def _source_port_for(row: Mapping[str, object]) -> str | None:
    unit = row["unit"]
    if unit == "requests":
        return _SOURCE_PORT_BY_PROVIDER.get(row["provider"] or "", "tools")
    return _SOURCE_PORT_BY_UNIT.get(unit)


def _dimension_values(row: Mapping[str, object]) -> dict[str, int]:
    unit = row["unit"]
    quantity = int(row["quantity"] or 0)
    if unit in ("embeddings", "embedding"):
        return {"embedding_count": quantity}
    if unit == "rerank":
        return {"rerank_count": quantity}
    if unit == "requests":
        return {"request_count": quantity}
    if unit == "vectors":
        return {"vector_count": quantity}
    if unit == "bytes":
        return {"storage_bytes": quantity}
    if unit == "ms":
        return {"latency_ms": quantity}
    return {}


def upgrade() -> None:
    op.add_column("run_cost_entries", sa.Column("source_port", sa.String(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("operation", sa.String(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("request_count", sa.Integer(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("embedding_count", sa.Integer(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("rerank_count", sa.Integer(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("vector_count", sa.Integer(), nullable=True))
    op.add_column("run_cost_entries", sa.Column("storage_bytes", sa.BigInteger(), nullable=True))
    op.create_index(
        "ix_run_cost_entries_source_port",
        "run_cost_entries",
        ["source_port"],
    )

    cost_entries = _cost_entries_table()
    connection = op.get_bind()
    rows = [dict(row) for row in connection.execute(sa.select(cost_entries)).mappings()]

    # Merge each step's single ms observation row into its sibling usage row.
    merged_ms_ids: set[str] = set()
    by_step: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        if row["step_id"] is not None:
            by_step.setdefault((str(row["run_id"]), str(row["step_id"])), []).append(row)
    for step_rows in by_step.values():
        ms_rows = [r for r in step_rows if r["unit"] == "ms" and r["entry_type"] == "usage"]
        main_rows = [
            r
            for r in step_rows
            if r["entry_type"] == "usage"
            and r["unit"] in ("tokens", "embeddings", "embedding", "rerank")
        ]
        if len(ms_rows) != 1 or len(main_rows) != 1:
            continue
        ms_row, main_row = ms_rows[0], main_rows[0]
        connection.execute(
            cost_entries.update()
            .where(cost_entries.c.id == main_row["id"])
            .values(latency_ms=int(ms_row["quantity"] or 0))
        )
        connection.execute(cost_entries.delete().where(cost_entries.c.id == ms_row["id"]))
        merged_ms_ids.add(str(ms_row["id"]))
        main_row["latency_ms"] = int(ms_row["quantity"] or 0)

    for row in rows:
        if str(row["id"]) in merged_ms_ids:
            continue
        values: dict[str, object] = _dimension_values(row)
        source_port = _source_port_for(row)
        if source_port:
            values["source_port"] = source_port
        if row.get("latency_ms") is not None:
            values["latency_ms"] = row["latency_ms"]
        if values:
            connection.execute(
                cost_entries.update().where(cost_entries.c.id == row["id"]).values(**values)
            )


def downgrade() -> None:
    op.drop_index("ix_run_cost_entries_source_port", table_name="run_cost_entries")
    for column in ("source_port", "operation", *_DIMENSION_COLUMNS):
        op.drop_column("run_cost_entries", column)
