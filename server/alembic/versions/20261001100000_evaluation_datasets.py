"""Evaluation datasets: regression case sets as versioned objects.

``regression_datasets`` gives each named set of cases a row of its own, with a
description and a revision that moves on every change, and
``regression_dataset_versions`` keeps what the set held at each revision.
Cases keep naming their set in ``regression_cases.dataset``, so the publish
gate, baselines and reports are untouched.

Sets that already exist are backfilled: every distinct (agent, dataset name)
among the cases gets a dataset row at the highest revision its cases carry,
and one version holding its active cases, so nothing is orphaned.

``regression_cases.source_run_id`` becomes nullable, since a case written or
imported into a dataset has no run it was frozen from.

Revision ID: 20261001100000
Revises: 20260927190000
Create Date: 2026-10-01
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

revision: str = "20261001100000"
down_revision: str | Sequence[str] | None = "20260927190000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DATASETS = "regression_datasets"
VERSIONS = "regression_dataset_versions"
CASES = "regression_cases"


def upgrade() -> None:
    op.create_table(
        DATASETS,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("subject_kind", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{DATASETS}_tenant_id", DATASETS, ["tenant_id"])
    op.create_index(f"ix_{DATASETS}_workspace_id", DATASETS, ["workspace_id"])
    op.create_index(f"ix_{DATASETS}_subject_kind", DATASETS, ["subject_kind"])
    op.create_index(f"ix_{DATASETS}_subject_id", DATASETS, ["subject_id"])
    op.create_index(f"ix_{DATASETS}_status", DATASETS, ["status"])
    op.create_index(
        "uq_regression_datasets_name",
        DATASETS,
        ["tenant_id", "workspace_id", "subject_kind", "subject_id", "name"],
        unique=True,
    )

    op.create_table(
        VERSIONS,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("dataset_id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("changes_json", sa.JSON(), nullable=True),
        sa.Column("note", sa.String(), nullable=False, server_default=""),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(f"ix_{VERSIONS}_tenant_id", VERSIONS, ["tenant_id"])
    op.create_index(f"ix_{VERSIONS}_workspace_id", VERSIONS, ["workspace_id"])
    op.create_index(f"ix_{VERSIONS}_dataset_id", VERSIONS, ["dataset_id"])
    op.create_index(
        "uq_regression_dataset_versions_revision",
        VERSIONS,
        ["tenant_id", "workspace_id", "dataset_id", "revision"],
        unique=True,
    )

    with op.batch_alter_table(CASES) as batch:
        batch.alter_column("source_run_id", existing_type=sa.String(), nullable=True)

    _backfill()


def _backfill() -> None:
    """One dataset per existing (agent, dataset name), with its current content."""
    bind = op.get_bind()
    cases = sa.table(
        CASES,
        sa.column("id", sa.String()),
        sa.column("tenant_id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("subject_kind", sa.String()),
        sa.column("subject_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("dataset", sa.String()),
        sa.column("dataset_revision", sa.Integer()),
        sa.column("input_snapshot_json", sa.JSON()),
        sa.column("expected_features_json", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
    )
    rows = bind.execute(
        sa.select(cases).order_by(cases.c.created_at, cases.c.id)
    ).all()

    groups: dict[tuple[str, str, str, str, str], list] = {}
    for row in rows:
        key = (
            row.tenant_id,
            row.workspace_id,
            row.subject_kind,
            row.subject_id,
            row.dataset,
        )
        groups.setdefault(key, []).append(row)
    if not groups:
        return

    datasets = sa.table(
        DATASETS,
        sa.column("id", sa.String()),
        sa.column("tenant_id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("subject_kind", sa.String()),
        sa.column("subject_id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("revision", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    versions = sa.table(
        VERSIONS,
        sa.column("id", sa.String()),
        sa.column("tenant_id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("dataset_id", sa.String()),
        sa.column("revision", sa.Integer()),
        sa.column("case_count", sa.Integer()),
        sa.column("content_hash", sa.String()),
        sa.column("snapshot_json", sa.JSON()),
        sa.column("changes_json", sa.JSON()),
        sa.column("note", sa.String()),
        sa.column("created_at", sa.DateTime()),
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for (tenant_id, workspace_id, subject_kind, subject_id, name), members in groups.items():
        dataset_id = f"regds_id_{uuid.uuid4().hex}"
        active = [row for row in members if row.status == "active"]
        snapshot = [_case_document(row) for row in active]
        bind.execute(
            sa.insert(datasets).values(
                id=dataset_id,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                subject_kind=subject_kind,
                subject_id=subject_id,
                name=name,
                description="",
                revision=max((int(row.dataset_revision or 1) for row in members), default=1),
                status="active",
                created_at=min(row.created_at for row in members),
                updated_at=now,
            )
        )
        bind.execute(
            sa.insert(versions).values(
                id=f"regdsv_id_{uuid.uuid4().hex}",
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                dataset_id=dataset_id,
                revision=max((int(row.dataset_revision or 1) for row in members), default=1),
                case_count=len(snapshot),
                content_hash=_content_hash(snapshot),
                snapshot_json=snapshot,
                changes_json={"added": len(snapshot), "removed": 0, "changed": 0},
                note="Backfilled from existing cases",
                created_at=now,
            )
        )


def _case_document(row) -> dict:
    """The case as a dataset snapshot holds it; mirrors dataset_format.case_document."""
    snapshot = dict(row.input_snapshot_json or {})
    if set(snapshot) == {"input"} and isinstance(snapshot["input"], str):
        value = snapshot["input"]
    else:
        value = snapshot
    return {
        "name": row.name,
        "input": value,
        "expected_features": dict(row.expected_features_json or {}),
    }


def _content_hash(snapshot: list[dict]) -> str:
    """Mirrors dataset_format.content_hash."""
    ordered = sorted(snapshot, key=lambda item: str(item.get("name")))
    canonical = json.dumps(ordered, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def downgrade() -> None:
    op.execute(sa.text(f"UPDATE {CASES} SET source_run_id = '' WHERE source_run_id IS NULL"))
    with op.batch_alter_table(CASES) as batch:
        batch.alter_column("source_run_id", existing_type=sa.String(), nullable=False)
    op.drop_index("uq_regression_dataset_versions_revision", table_name=VERSIONS)
    op.drop_index(f"ix_{VERSIONS}_dataset_id", table_name=VERSIONS)
    op.drop_index(f"ix_{VERSIONS}_workspace_id", table_name=VERSIONS)
    op.drop_index(f"ix_{VERSIONS}_tenant_id", table_name=VERSIONS)
    op.drop_table(VERSIONS)
    op.drop_index("uq_regression_datasets_name", table_name=DATASETS)
    op.drop_index(f"ix_{DATASETS}_status", table_name=DATASETS)
    op.drop_index(f"ix_{DATASETS}_subject_id", table_name=DATASETS)
    op.drop_index(f"ix_{DATASETS}_subject_kind", table_name=DATASETS)
    op.drop_index(f"ix_{DATASETS}_workspace_id", table_name=DATASETS)
    op.drop_index(f"ix_{DATASETS}_tenant_id", table_name=DATASETS)
    op.drop_table(DATASETS)
