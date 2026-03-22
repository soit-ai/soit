"""bootstrap_admin

Create a default admin user, tenant, and workspace for local deployments.

Usage:
    python scripts/bootstrap_admin.py --email admin@example.com --password changeme123 --name Admin
"""

from __future__ import annotations

import argparse

from app.infra.db.session import get_db_sync
from app.wiring.services import build_identity_service
from app.modules.identity.application.schemas import UserCreate


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap admin user/tenant/workspace.")
    parser.add_argument("--email", required=True, help="Admin email.")
    parser.add_argument("--password", required=True, help="Admin password (min 8 chars).")
    parser.add_argument("--name", default="Admin", help="Admin display name.")
    parser.add_argument("--tenant-name", default="default", help="Tenant name.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    db = get_db_sync()
    try:
        service = build_identity_service(db=db)
        existing = service.user_repo.get_by_email(args.email)
        if existing:
            print("User already exists. Skipping bootstrap.")
            return 0

        user, tenant, access_token, workspace_id = service.register_user(
            UserCreate(email=args.email, password=args.password, name=args.name),
            tenant_name=args.tenant_name,
        )

        print("Bootstrap completed.")
        print(f"user_id={user.id}")
        print(f"tenant_id={tenant.id}")
        print(f"workspace_id={workspace_id}")
        print(f"access_token={access_token}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
