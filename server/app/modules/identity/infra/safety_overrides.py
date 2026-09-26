"""A workspace's content safety overrides, read for the kernel's rules."""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.infra.db.session import get_async_session_local
from app.modules.identity.domain.models import Workspace


async def workspace_pii_actions(
    db: AsyncSession | None,
    tenant_id: str,
    workspace_id: str,
) -> dict[str, str | None]:
    """The workspace's PII action per direction; None entries follow the deployment.

    Reads through the caller's session when it has one, so a run sees the
    same database its trace is written to; otherwise opens and closes its own.
    """

    session = db if db is not None else get_async_session_local()()
    try:
        row = (
            await session.exec(
                select(Workspace.pii_action_inbound, Workspace.pii_action_outbound).where(
                    Workspace.id == workspace_id,
                    Workspace.tenant_id == tenant_id,
                )
            )
        ).first()
    finally:
        if db is None:
            await session.close()
    if row is None:
        return {}
    inbound, outbound = row
    return {"inbound": inbound, "outbound": outbound}
