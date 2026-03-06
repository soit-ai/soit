"""rebuild_projections

Rebuild workflow projections for app versions.
"""

from __future__ import annotations

import argparse

from sqlalchemy import select, and_

from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.modules.appcenter.application.publish_service import AppPublishService
from app.modules.appcenter.domain.models import AppVersion


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild app projections.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--app-id")
    parser.add_argument("--version-id")
    parser.add_argument("--spec-schema", help="Filter by spec schema (workflow.v1/chat.v1/bot.v1).")
    parser.add_argument("--all", action="store_true", help="Rebuild projections for all matching versions.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    ctx = RequestContext(
        tenant_id=args.tenant_id,
        workspace_id=args.workspace_id,
        user_id=args.user_id,
    )
    db = get_db_sync()
    try:
        service = AppPublishService(db, ctx)
        if args.version_id:
            app_id = args.app_id
            if not app_id:
                version = db.get(AppVersion, args.version_id)
                if not version:
                    print("Version not found.")
                    return 1
                app_id = version.app_id
            service.rebuild_projections(app_id, args.version_id)
            print(f"Rebuilt projections for version={args.version_id}")
            return 0

        if args.app_id:
            versions = db.exec(
                select(AppVersion).where(
                    and_(
                        AppVersion.app_id == args.app_id,
                        AppVersion.tenant_id == ctx.tenant_id,
                        AppVersion.workspace_id == ctx.workspace_id,
                    )
                )
            ).all()
            for row in versions:
                version = row if isinstance(row, AppVersion) else row[0]
                service.rebuild_projections(args.app_id, version.id)
            print(f"Rebuilt projections for app={args.app_id}")
            return 0

        if args.all:
            spec_schemas = [args.spec_schema] if args.spec_schema else ["workflow.v1", "chat.v1", "bot.v1", "agent.v1"]
            versions = db.exec(
                select(AppVersion).where(
                    and_(
                        AppVersion.tenant_id == ctx.tenant_id,
                        AppVersion.workspace_id == ctx.workspace_id,
                        AppVersion.spec_schema.in_(spec_schemas),
                    )
                )
            ).all()
            for row in versions:
                version = row if isinstance(row, AppVersion) else row[0]
                service.rebuild_projections(version.app_id, version.id)
            print("Rebuilt projections for all matching versions.")
            return 0

        print("No targets specified. Use --version-id, --app-id, or --all.")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
