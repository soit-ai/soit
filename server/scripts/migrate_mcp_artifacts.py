"""Migrate enabled MCP artifacts to the official streamable HTTP contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import re

from sqlalchemy import select

from app.adapters.secrets.vault import VaultSecretsPort
from app.adapters.tools.mcp_migration import mcp_metadata_issues, migrate_mcp_metadata
from app.infra.db.session import get_db_sync
from app.modules.plugin.domain.models import PluginInstalledArtifact


def _secret_stem(artifact: PluginInstalledArtifact) -> str:
    raw = f"{artifact.tenant_id}_{artifact.workspace_id}_{artifact.artifact_ref}"
    return re.sub(r"[^A-Za-z0-9_-]+", "_", raw).strip("_").lower()


async def run(*, apply: bool) -> int:
    db = get_db_sync()
    secrets = VaultSecretsPort()
    report: list[dict[str, object]] = []
    try:
        rows = db.exec(select(PluginInstalledArtifact)).all()
        for raw_row in rows:
            artifact = (
                raw_row[0]
                if hasattr(raw_row, "__getitem__") and not isinstance(raw_row, PluginInstalledArtifact)
                else raw_row
            )
            if artifact.artifact_kind != "mcp_server":
                continue
            issues = mcp_metadata_issues(artifact.metadata_json or {})
            if not issues:
                continue
            stem = _secret_stem(artifact)
            migrated, secret_writes = migrate_mcp_metadata(
                artifact.metadata_json or {},
                bearer_secret_ref=f"secret:{stem}_bearer",
                api_key_secret_ref=f"secret:{stem}_api_key",
            )
            report.append(
                {
                    "artifact_ref": artifact.artifact_ref,
                    "issues": issues,
                    "secret_refs": [secret_ref for secret_ref, _ in secret_writes],
                }
            )
            if apply:
                for secret_ref, value in secret_writes:
                    await secrets.set_secret(secret_ref=secret_ref, value=value)
                artifact.metadata_json = migrated
                db.add(artifact)
        if apply:
            db.commit()
        else:
            db.rollback()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(json.dumps({"mode": "apply" if apply else "dry-run", "artifacts": report}, indent=2))
    return len(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write secret values to Vault and update artifact metadata",
    )
    args = parser.parse_args()
    asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    main()
