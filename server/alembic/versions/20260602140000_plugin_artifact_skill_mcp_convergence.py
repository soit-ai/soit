"""plugin artifact skill/mcp convergence

Revision ID: 20260602140000_plugin_artifact_skill_mcp_convergence
Revises: 20260602130000_plugin_unified_lifecycle
Create Date: 2026-06-02 14:00:00.000000
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op


revision = "20260602140000_plugin_artifact_skill_mcp_convergence"
down_revision = "20260602130000"
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


def _first(conn, table: sa.Table, where_clause):
    return conn.execute(sa.select(table).where(where_clause).limit(1)).mappings().first()


def _skill_spec(conn, skill_versions: sa.Table | None, skill: dict) -> dict:
    if skill_versions is not None:
        for version_id_key in ("published_version_id", "current_version_id"):
            version_id = skill.get(version_id_key)
            if not version_id:
                continue
            row = conn.execute(sa.select(skill_versions).where(skill_versions.c.id == version_id).limit(1)).mappings().first()
            if row and isinstance(row.get("spec_json"), dict):
                return row["spec_json"]
        row = (
            conn.execute(
                sa.select(skill_versions)
                .where(skill_versions.c.skill_id == skill["id"])
                .order_by(skill_versions.c.created_at.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if row and isinstance(row.get("spec_json"), dict):
            return row["spec_json"]
    if isinstance(skill.get("spec_json"), dict):
        return skill["spec_json"]
    metadata = skill.get("metadata_json") or {}
    if isinstance(metadata, dict):
        for key in ("spec_json", "spec"):
            if isinstance(metadata.get(key), dict):
                return metadata[key]
    return {}


def _create_plugin_bundle(
    conn,
    *,
    plugins: sa.Table,
    plugin_versions: sa.Table,
    plugin_installations: sa.Table,
    plugin_installed_artifacts: sa.Table,
    tenant_id: str,
    workspace_id: str,
    plugin_name: str,
    plugin_type: str,
    artifact_kind: str,
    artifact_ref: str,
    artifact_metadata: dict,
    enabled: bool,
    created_by: str | None = None,
) -> None:
    existing = _first(
        conn,
        plugins,
        sa.and_(
            plugins.c.tenant_id == tenant_id,
            plugins.c.workspace_id == workspace_id,
            plugins.c.name == plugin_name,
        ),
    )
    if existing:
        return

    now = _now()
    plugin_id = _id("plg")
    version_id = _id("plgv")
    installation_id = _id("inst")
    export_key = "skills" if artifact_kind == "skill" else "mcp_servers"
    spec = {
        "name": plugin_name,
        "publisher": "workspace",
        "version": "1.0.0",
        "plugin_type": plugin_type,
        "runtime_level": "L0",
        "capabilities": [f"{artifact_kind}s" if artifact_kind != "mcp_server" else "mcp_servers"],
        "exports": {export_key: [artifact_ref]},
        "permissions": {},
        "integrity": {"digest": "sha256:migrated"},
    }
    manifest = {"name": plugin_name, "version": "1.0.0", "runtime": {"type": "http"}, "spec": spec}

    conn.execute(
        plugins.insert().values(
            id=plugin_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            name=plugin_name,
            version="1.0.0",
            publisher="workspace",
            plugin_type=plugin_type,
            status="active" if enabled else "disabled",
            description=artifact_metadata.get(artifact_kind, {}).get("description"),
            spec_json=spec,
            manifest_json=manifest,
            metadata_json={"migrated_from": artifact_kind},
            publish_status="published",
            installed_count=1,
            current_version_id=version_id,
            published_version_id=version_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
    )
    conn.execute(
        plugin_versions.insert().values(
            id=version_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            plugin_id=plugin_id,
            version=1,
            package_version="1.0.0",
            status="published",
            spec_schema="plugin.v1",
            spec_json=spec,
            manifest_json=manifest,
            package_sha256=None,
            artifact_summary_json={export_key: [artifact_ref]},
            metadata_json={"migrated_from": artifact_kind},
            created_by=created_by,
            created_at=now,
        )
    )
    conn.execute(
        plugin_installations.insert().values(
            id=installation_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            plugin_id=plugin_id,
            plugin_version_id=version_id,
            enabled=enabled,
            state="installed" if enabled else "disabled",
            installed_by=created_by,
            config_json={"enabled": enabled, "migrated": True},
            created_at=now,
            updated_at=now,
        )
    )
    conn.execute(
        plugin_installed_artifacts.insert().values(
            id=_id("plga"),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            plugin_id=plugin_id,
            plugin_version_id=version_id,
            installation_id=installation_id,
            artifact_kind=artifact_kind,
            artifact_ref=artifact_ref,
            artifact_id=artifact_ref,
            artifact_version_id=None,
            state="enabled" if enabled else "disabled",
            enabled=enabled,
            metadata_json=artifact_metadata,
            created_at=now,
            updated_at=now,
        )
    )


def upgrade() -> None:
    conn = op.get_bind()
    metadata = sa.MetaData()
    required = ["plugins", "plugin_versions", "plugin_installations", "plugin_installed_artifacts"]
    if any(name not in _tables(conn) for name in required):
        return

    plugins = _table(metadata, conn, "plugins")
    plugin_versions = _table(metadata, conn, "plugin_versions")
    plugin_installations = _table(metadata, conn, "plugin_installations")
    plugin_installed_artifacts = _table(metadata, conn, "plugin_installed_artifacts")
    skills = _table(metadata, conn, "skills")
    skill_versions = _table(metadata, conn, "skill_versions")
    mcp_servers = _table(metadata, conn, "mcp_servers")
    assert plugins is not None and plugin_versions is not None and plugin_installations is not None and plugin_installed_artifacts is not None

    if skills is not None:
        for row in conn.execute(sa.select(skills)).mappings():
            skill = dict(row)
            if skill.get("deleted_at") is not None or skill.get("status") == "archived":
                continue
            spec_json = _skill_spec(conn, skill_versions, skill)
            name = str(skill.get("name") or skill["id"])
            artifact = {
                "skill": {
                    "name": name,
                    "description": skill.get("description"),
                    "category": skill.get("category"),
                    "visibility": skill.get("visibility"),
                    "metadata_json": skill.get("metadata_json") or {},
                    "spec_json": spec_json,
                }
            }
            _create_plugin_bundle(
                conn,
                plugins=plugins,
                plugin_versions=plugin_versions,
                plugin_installations=plugin_installations,
                plugin_installed_artifacts=plugin_installed_artifacts,
                tenant_id=skill["tenant_id"],
                workspace_id=skill["workspace_id"],
                plugin_name=f"workspace-skill-{name}",
                plugin_type="skill",
                artifact_kind="skill",
                artifact_ref=f"skill:{name}",
                artifact_metadata=artifact,
                enabled=skill.get("status") != "disabled",
                created_by=skill.get("created_by"),
            )

    if mcp_servers is not None:
        for row in conn.execute(sa.select(mcp_servers)).mappings():
            server = dict(row)
            if server.get("deleted_at") is not None or server.get("status") == "archived":
                continue
            name = str(server.get("name") or server["id"])
            artifact = {
                "mcp_server": {
                    "name": name,
                    "description": server.get("description"),
                    "transport": server.get("transport"),
                    "endpoint": server.get("endpoint"),
                    "auth_config_json": server.get("auth_config_json") or {},
                    "capabilities_json": server.get("capabilities_json") or {},
                    "metadata_json": server.get("metadata_json") or {},
                }
            }
            _create_plugin_bundle(
                conn,
                plugins=plugins,
                plugin_versions=plugin_versions,
                plugin_installations=plugin_installations,
                plugin_installed_artifacts=plugin_installed_artifacts,
                tenant_id=server["tenant_id"],
                workspace_id=server["workspace_id"],
                plugin_name=f"workspace-mcp-{name}",
                plugin_type="mcp",
                artifact_kind="mcp_server",
                artifact_ref=f"mcp_server:{name}",
                artifact_metadata=artifact,
                enabled=bool(server.get("enabled")) and server.get("status") != "disabled",
                created_by=server.get("created_by"),
            )

    for table_name in ("skill_publishes", "skill_versions", "mcp_servers", "skills"):
        if table_name in _tables(conn):
            op.drop_table(table_name)


def downgrade() -> None:
    raise NotImplementedError(
        "Plugin artifact skill/MCP convergence is irreversible; legacy skill/mcp tables are not restored."
    )
