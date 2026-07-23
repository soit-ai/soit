"""Migrate public and runtime secret references to scoped opaque IDs.

Revision ID: 20260723160000
Revises: 20260718140000
Create Date: 2026-07-23 16:00:00

"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

import sqlalchemy as sa

from alembic import op

revision = "20260723160000"
down_revision = "20260718140000"
branch_labels = None
depends_on = None

_SECRET_ID_PATTERN = re.compile(r"^sec_[A-Za-z0-9][A-Za-z0-9_-]{2,124}$")
_LEGACY_TO_CURRENT = {
    "secret_ref": "secret_id",
    "secret_refs": "secret_ids",
    "credential_ref": "credential_secret_id",
}
_CURRENT_TO_LEGACY = {value: key for key, value in _LEGACY_TO_CURRENT.items()}

_JSON_TARGETS = (
    ("agents", "runtime_config_json"),
    ("agent_versions", "spec_json"),
    ("workflow_versions", "spec_json"),
    ("plugins", "spec_json"),
    ("plugins", "manifest_json"),
    ("plugins", "metadata_json"),
    ("plugin_versions", "spec_json"),
    ("plugin_versions", "manifest_json"),
    ("plugin_versions", "artifact_summary_json"),
    ("plugin_versions", "metadata_json"),
    ("plugin_installations", "config_json"),
    ("plugin_installed_artifacts", "metadata_json"),
    ("providers", "auth_config_json"),
    ("providers", "runtime_config_json"),
)


def _migrate_payload(
    value: Any,
    resolve_secret_id: Callable[[str], str],
) -> Any:
    """Recursively canonicalize known secret fields and validate their scope."""
    if isinstance(value, list):
        return [_migrate_payload(item, resolve_secret_id) for item in value]
    if not isinstance(value, dict):
        return value

    migrated: dict[str, Any] = {}
    for key, item in value.items():
        target_key = _LEGACY_TO_CURRENT.get(key, key)
        if target_key in {"secret_id", "credential_secret_id"}:
            migrated_value = resolve_secret_id(str(item))
        elif target_key == "secret_ids":
            if not isinstance(item, list):
                raise RuntimeError("Scoped secret migration requires a secret ID list")
            migrated_value = [resolve_secret_id(str(entry)) for entry in item]
        elif target_key == "secret_bindings":
            if not isinstance(item, dict):
                raise RuntimeError("Scoped secret migration requires an object binding")
            migrated_value = {
                str(parameter): resolve_secret_id(str(secret_id))
                for parameter, secret_id in item.items()
            }
        elif target_key == "secrets" and isinstance(item, list):
            migrated_value = [resolve_secret_id(str(entry)) for entry in item]
        else:
            migrated_value = _migrate_payload(item, resolve_secret_id)

        if target_key in migrated and migrated[target_key] != migrated_value:
            raise RuntimeError("Scoped secret migration found conflicting secret fields")
        migrated[target_key] = migrated_value
    return migrated


def _restore_payload(value: Any) -> Any:
    """Restore the legacy field shape for a reversible downgrade."""
    if isinstance(value, list):
        return [_restore_payload(item) for item in value]
    if not isinstance(value, dict):
        return value

    restored: dict[str, Any] = {}
    for key, item in value.items():
        target_key = _CURRENT_TO_LEGACY.get(key, key)
        if key in {"secret_id", "credential_secret_id"}:
            restored_value = _legacy_ref(str(item))
        elif key == "secret_ids":
            restored_value = [_legacy_ref(str(entry)) for entry in item]
        elif key == "secret_bindings":
            restored_value = {
                str(parameter): _legacy_ref(str(secret_id))
                for parameter, secret_id in item.items()
            }
        elif key == "secrets" and isinstance(item, list):
            restored_value = [_legacy_ref(str(entry)) for entry in item]
        else:
            restored_value = _restore_payload(item)
        restored[target_key] = restored_value
    return restored


def _legacy_ref(secret_id: str) -> str:
    return secret_id if secret_id.startswith("secret:") else f"secret:{secret_id}"


def _scoped_resolver(
    bind: sa.Connection,
    *,
    tenant_id: str,
    workspace_id: str,
    location: str,
) -> Callable[[str], str]:
    secrets = sa.table(
        "secrets",
        sa.column("id", sa.String()),
        sa.column("tenant_id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column("deleted_at", sa.DateTime()),
    )

    def resolve(raw_value: str) -> str:
        candidate = raw_value.removeprefix("secret:").strip()
        if not _SECRET_ID_PATTERN.fullmatch(candidate):
            raise RuntimeError(
                f"Scoped secret migration rejected an invalid value at {location}"
            )
        exists = bind.execute(
            sa.select(secrets.c.id).where(
                secrets.c.id == candidate,
                secrets.c.tenant_id == tenant_id,
                secrets.c.workspace_id == workspace_id,
                secrets.c.deleted_at.is_(None),
            )
        ).first()
        if exists is None:
            raise RuntimeError(
                f"Scoped secret migration could not resolve an in-scope Secret at {location}"
            )
        return candidate

    return resolve


def _migrate_json_columns(bind: sa.Connection) -> None:
    for table_name, column_name in _JSON_TARGETS:
        table = sa.table(
            table_name,
            sa.column("id", sa.String()),
            sa.column("tenant_id", sa.String()),
            sa.column("workspace_id", sa.String()),
            sa.column(column_name, sa.JSON()),
        )
        rows = bind.execute(
            sa.select(
                table.c.id,
                table.c.tenant_id,
                table.c.workspace_id,
                table.c[column_name],
            )
        ).mappings()
        for row in rows:
            payload = row[column_name]
            if payload is None:
                continue
            location = f"{table_name}.{column_name}:{row['id']}"
            migrated = _migrate_payload(
                payload,
                _scoped_resolver(
                    bind,
                    tenant_id=row["tenant_id"],
                    workspace_id=row["workspace_id"],
                    location=location,
                ),
            )
            if migrated != payload:
                bind.execute(
                    sa.update(table)
                    .where(table.c.id == row["id"])
                    .values({column_name: migrated})
                )


def _restore_json_columns(bind: sa.Connection) -> None:
    for table_name, column_name in _JSON_TARGETS:
        table = sa.table(
            table_name,
            sa.column("id", sa.String()),
            sa.column(column_name, sa.JSON()),
        )
        rows = bind.execute(
            sa.select(table.c.id, table.c[column_name])
        ).mappings()
        for row in rows:
            payload = row[column_name]
            if payload is None:
                continue
            restored = _restore_payload(payload)
            if restored != payload:
                bind.execute(
                    sa.update(table)
                    .where(table.c.id == row["id"])
                    .values({column_name: restored})
                )


def _migrate_scalar_column(
    bind: sa.Connection,
    *,
    table_name: str,
    column_name: str,
) -> None:
    table = sa.table(
        table_name,
        sa.column("id", sa.String()),
        sa.column("tenant_id", sa.String()),
        sa.column("workspace_id", sa.String()),
        sa.column(column_name, sa.String()),
    )
    rows = bind.execute(
        sa.select(
            table.c.id,
            table.c.tenant_id,
            table.c.workspace_id,
            table.c[column_name],
        ).where(table.c[column_name].is_not(None))
    ).mappings()
    for row in rows:
        location = f"{table_name}.{column_name}:{row['id']}"
        secret_id = _scoped_resolver(
            bind,
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            location=location,
        )(row[column_name])
        if secret_id != row[column_name]:
            bind.execute(
                sa.update(table)
                .where(table.c.id == row["id"])
                .values({column_name: secret_id})
            )


def _restore_scalar_column(
    bind: sa.Connection,
    *,
    table_name: str,
    column_name: str,
) -> None:
    table = sa.table(
        table_name,
        sa.column("id", sa.String()),
        sa.column(column_name, sa.String()),
    )
    rows = bind.execute(
        sa.select(table.c.id, table.c[column_name]).where(
            table.c[column_name].is_not(None)
        )
    ).mappings()
    for row in rows:
        bind.execute(
            sa.update(table)
            .where(table.c.id == row["id"])
            .values({column_name: _legacy_ref(row[column_name])})
        )


def upgrade() -> None:
    bind = op.get_bind()
    _migrate_json_columns(bind)
    _migrate_scalar_column(
        bind,
        table_name="providers",
        column_name="credential_ref",
    )
    _migrate_scalar_column(
        bind,
        table_name="notification_endpoints",
        column_name="secret_ref",
    )


def downgrade() -> None:
    bind = op.get_bind()
    _restore_json_columns(bind)
    _restore_scalar_column(
        bind,
        table_name="providers",
        column_name="credential_ref",
    )
    _restore_scalar_column(
        bind,
        table_name="notification_endpoints",
        column_name="secret_ref",
    )
