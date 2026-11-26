"""bootstrap_admin

Create the admin user, and the organization (tenant) and workspace they own,
for local deployments.

Usage:
    python scripts/bootstrap_admin.py --email admin@example.com --password changeme123 --name Admin
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.infra.db.session import get_async_session_local
from app.kernel.identity.rbac import TENANT_ROLE_OWNER
from app.modules.identity.application.schemas import UserCreate
from app.settings.settings import settings
from app.wiring.services import build_identity_service


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap admin user/tenant/workspace.")
    parser.add_argument("--email", required=True, help="Admin email.")
    parser.add_argument("--password", required=True, help="Admin password (min 8 chars).")
    parser.add_argument("--name", default="Admin", help="Admin display name.")
    parser.add_argument("--tenant-name", default="default", help="Tenant name.")
    return parser.parse_args()


SHIPPED_DEFAULT_PASSWORDS = frozenset({"changeme123"})
"""Admin passwords written in the compose files and docs, refused in production."""


async def main() -> int:
    args = _parse_args()
    if (settings.environment or "").strip().lower() == "production" and (
        args.password in SHIPPED_DEFAULT_PASSWORDS
    ):
        print(
            "Refusing to create the admin with the documented default password in "
            "production. Set BOOTSTRAP_ADMIN_PASSWORD (docker/init.sh writes one).",
            file=sys.stderr,
        )
        return 2
    db = get_async_session_local()()
    try:
        service = build_identity_service(db=db)
        existing = await service.user_repo.get_by_email(args.email)
        if existing:
            print("User already exists. Skipping bootstrap.")
            return 0

        # The admin owns the organization: they found it on a fresh
        # deployment, and in a single-organization deployment that already
        # has one they join it as an owner rather than a member.
        user, tenant, access_token, workspace_id, _refresh = await service.register_user(
            UserCreate(email=args.email, password=args.password, name=args.name),
            tenant_name=args.tenant_name,
            organization_role=TENANT_ROLE_OWNER,
        )

        print("Bootstrap completed.")
        print(f"user_id={user.id}")
        print(f"tenant_id={tenant.id}")
        print(f"workspace_id={workspace_id}")
        print(f"access_token={access_token}")
        return 0
    finally:
        await db.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    raise SystemExit(asyncio.run(main()))
