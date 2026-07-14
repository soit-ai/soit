"""table convergence for audit, outbox dlq, observe checkpoints, and modelhub removals

Revision ID: 20260604120000_table_convergence
Revises: 20260603110000_knowledge_document_source_kind
Create Date: 2026-06-04 12:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "20260604120000_table_convergence"
down_revision = "20260603110000_knowledge_document_source_kind"
branch_labels = None
depends_on = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def _tables(conn) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def _columns(conn, table_name: str) -> set[str]:
    if table_name not in _tables(conn):
        return set()
    return {column["name"] for column in sa.inspect(conn).get_columns(table_name)}


def _table(metadata: sa.MetaData, conn, table_name: str) -> sa.Table | None:
    if table_name not in _tables(conn):
        return None
    return sa.Table(table_name, metadata, autoload_with=conn)


def _create_audit_events(conn) -> None:
    if "audit_events" in _tables(conn):
        return
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("workspace_id", sa.String(), nullable=True, index=True),
        sa.Column("event_type", sa.String(), nullable=False, index=True),
        sa.Column("resource_type", sa.String(), nullable=False, index=True),
        sa.Column("resource_id", sa.String(), nullable=True, index=True),
        sa.Column("operation", sa.String(), nullable=False, index=True),
        sa.Column("actor_user_id", sa.String(), nullable=True, index=True),
        sa.Column("subject_user_id", sa.String(), nullable=True, index=True),
        sa.Column("scope", sa.String(), nullable=True, index=True),
        sa.Column("payload_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_events_scope_created", "audit_events", ["tenant_id", "workspace_id", "created_at"])
    op.create_index("ix_audit_events_resource", "audit_events", ["tenant_id", "workspace_id", "resource_type", "resource_id"])
    op.create_index("ix_audit_events_event_type_created", "audit_events", ["event_type", "created_at"])


def _ensure_outbox_failed_consumer(conn) -> None:
    if "event_outbox" in _tables(conn) and "failed_consumer_name" not in _columns(conn, "event_outbox"):
        op.add_column("event_outbox", sa.Column("failed_consumer_name", sa.String(), nullable=True))
        op.create_index("ix_event_outbox_failed_consumer_name", "event_outbox", ["failed_consumer_name"])


def _backfill_observe_checkpoints(conn, metadata: sa.MetaData) -> None:
    observe = _table(metadata, conn, "observe_projection_records")
    checkpoints = _table(metadata, conn, "event_consumer_checkpoint")
    if observe is None or checkpoints is None:
        return
    for row in conn.execute(sa.select(observe)).mappings():
        exists = conn.execute(
            sa.select(checkpoints.c.id)
            .where(
                sa.and_(
                    checkpoints.c.consumer_name == row["consumer_name"],
                    checkpoints.c.event_id == row["event_id"],
                )
            )
            .limit(1)
        ).first()
        if exists:
            continue
        conn.execute(
            checkpoints.insert().values(
                id=_id("chk"),
                consumer_name=row["consumer_name"],
                event_id=row["event_id"],
                processed_at=row.get("created_at") or _now(),
                result="observe_projection",
                error_message=None,
            )
        )


def _backfill_dead_letters(conn, metadata: sa.MetaData) -> None:
    dead_letters = _table(metadata, conn, "dead_letter_events")
    outbox = _table(metadata, conn, "event_outbox")
    if dead_letters is None or outbox is None:
        return
    for row in conn.execute(sa.select(dead_letters)).mappings():
        message = row.get("error_message")
        conn.execute(
            outbox.update()
            .where(outbox.c.event_id == row["event_id"])
            .values(
                status="failed",
                failed_consumer_name=row.get("consumer_name"),
                last_error=message,
                processed_at=row.get("failed_at") or _now(),
            )
        )


def _backfill_audit_events(conn, metadata: sa.MetaData) -> None:
    audit_events = _table(metadata, conn, "audit_events")
    if audit_events is None:
        return
    resource_grants = _table(metadata, conn, "resource_grant_audits")
    if resource_grants is not None:
        for row in conn.execute(sa.select(resource_grants)).mappings():
            conn.execute(
                audit_events.insert().values(
                    id=_id("aud"),
                    tenant_id=row["tenant_id"],
                    workspace_id=row["workspace_id"],
                    event_type="identity.resource_grant.changed",
                    resource_type=row["resource_type"],
                    resource_id=row["resource_id"],
                    operation=row["operation"],
                    actor_user_id=row.get("created_by"),
                    subject_user_id=row.get("user_id"),
                    scope="workspace",
                    payload_json={"actions": row.get("actions") or []},
                    created_at=row["created_at"],
                )
            )
    egress = _table(metadata, conn, "egress_policy_audits")
    if egress is not None:
        for row in conn.execute(sa.select(egress)).mappings():
            conn.execute(
                audit_events.insert().values(
                    id=_id("aud"),
                    tenant_id=row["tenant_id"],
                    workspace_id=row.get("workspace_id"),
                    event_type="security.egress_policy.updated",
                    resource_type="egress_policy",
                    resource_id=row["scope"],
                    operation="update",
                    actor_user_id=row.get("created_by"),
                    subject_user_id=None,
                    scope=row["scope"],
                    payload_json={
                        "allowlist": row.get("allowlist") or [],
                        "blocklist": row.get("blocklist") or [],
                    },
                    created_at=row["created_at"],
                )
            )


def _backfill_modelhub_removed(conn, metadata: sa.MetaData) -> None:
    tombstones = _table(metadata, conn, "provider_model_tombstones")
    provider_models = _table(metadata, conn, "provider_models")
    platform_models = _table(metadata, conn, "platform_models")
    providers = _table(metadata, conn, "providers")
    if tombstones is None or provider_models is None or platform_models is None or providers is None:
        return
    now = _now()
    for row in conn.execute(sa.select(tombstones)).mappings():
        existing = conn.execute(
            sa.select(provider_models)
            .where(
                sa.and_(
                    provider_models.c.tenant_id == row["tenant_id"],
                    provider_models.c.workspace_id == row["workspace_id"],
                    provider_models.c.provider_id == row["provider_id"],
                    provider_models.c.platform_model_id == row["platform_model_id"],
                )
            )
            .limit(1)
        ).mappings().first()
        if existing:
            conn.execute(
                provider_models.update()
                .where(provider_models.c.id == existing["id"])
                .values(status="removed", sync_status="user_removed", updated_at=row.get("deleted_at") or now)
            )
            continue
        provider = conn.execute(
            sa.select(providers).where(providers.c.id == row["provider_id"]).limit(1)
        ).mappings().first()
        platform = conn.execute(
            sa.select(platform_models).where(platform_models.c.id == row["platform_model_id"]).limit(1)
        ).mappings().first()
        if provider is None or platform is None:
            continue
        conn.execute(
            provider_models.insert().values(
                id=_id("pmod"),
                tenant_id=row["tenant_id"],
                workspace_id=row["workspace_id"],
                provider_id=row["provider_id"],
                provider_kind=provider["kind"],
                model_id=platform["model_id"],
                display_name=platform.get("display_name"),
                capabilities_json=platform.get("capabilities_json"),
                config_json=None,
                context_window=platform.get("context_window"),
                max_output_tokens=platform.get("max_output_tokens"),
                lifecycle_status=platform.get("lifecycle_status"),
                raw_meta=platform.get("raw_meta"),
                status="removed",
                source="platform",
                platform_model_id=row["platform_model_id"],
                sync_status="user_removed",
                user_overrides_json=None,
                last_synced_at=None,
                created_at=row.get("deleted_at") or now,
                updated_at=row.get("deleted_at") or now,
            )
        )


def _drop_legacy_tables(conn) -> None:
    for table_name in (
        "observe_projection_records",
        "dead_letter_events",
        "provider_model_tombstones",
        "resource_grant_audits",
        "egress_policy_audits",
    ):
        if table_name in _tables(conn):
            op.drop_table(table_name)


def upgrade() -> None:
    conn = op.get_bind()
    metadata = sa.MetaData()
    _create_audit_events(conn)
    _ensure_outbox_failed_consumer(conn)
    _backfill_observe_checkpoints(conn, metadata)
    _backfill_dead_letters(conn, metadata)
    _backfill_audit_events(conn, metadata)
    _backfill_modelhub_removed(conn, metadata)
    _drop_legacy_tables(conn)


def downgrade() -> None:
    raise NotImplementedError(
        "Table convergence is irreversible; unified checkpoint, outbox, audit, and provider model states are canonical."
    )
