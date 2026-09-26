"""The workspace content capture setting, read for trace writers."""

from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.identity.domain.models import Workspace


async def workspace_content_capture(
    db: AsyncSession,
    tenant_id: str,
    workspace_id: str,
) -> str | None:
    """The workspace's capture mode, or None when there is no such workspace."""

    result = await db.exec(
        select(Workspace.content_capture).where(
            Workspace.id == workspace_id,
            Workspace.tenant_id == tenant_id,
        )
    )
    return result.first()
