"""Which knowledge bases a workspace member can see.

``Knowledge.visibility`` decides who sees a knowledge base beyond its
workspace role ladder:

* ``private``: its creator, workspace owners and admins, and members with an
  explicit resource grant on it;
* ``workspace``: every member the role ladder admits;
* ``tenant``: reserved for cross-workspace sharing; until that ships it
  behaves as ``workspace``, which is never wider than what was declared.

Single-resource access is decided by the kernel permission check with the
visibility this module resolves; listings apply the same rule in SQL.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import exists, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    RESOURCE_KNOWLEDGE,
    VISIBILITY_PRIVATE,
    ResourceVisibility,
    sees_private_resources,
)
from app.modules.identity.domain.models import ResourceGrant
from app.modules.knowledge.domain.models import Knowledge

KNOWLEDGE_VISIBILITIES = ("private", "workspace", "tenant")
DEFAULT_KNOWLEDGE_VISIBILITY = "workspace"


def knowledge_visibility(knowledge: Knowledge | None) -> ResourceVisibility | None:
    """Visibility input for the kernel permission check."""

    if knowledge is None:
        return None
    return ResourceVisibility(
        visibility=str(knowledge.visibility or DEFAULT_KNOWLEDGE_VISIBILITY),
        created_by=knowledge.created_by,
    )


def visible_knowledge_clause(ctx: RequestContext) -> Any | None:
    """SQL filter for the knowledge bases ``ctx`` may list, or None for all."""

    if sees_private_resources(ctx):
        return None
    granted = exists().where(
        ResourceGrant.tenant_id == ctx.tenant_id,
        ResourceGrant.workspace_id == ctx.workspace_id,
        ResourceGrant.resource_type == RESOURCE_KNOWLEDGE,
        ResourceGrant.resource_id == Knowledge.id,
        ResourceGrant.user_id == ctx.user_id,
    )
    return or_(
        Knowledge.visibility != VISIBILITY_PRIVATE,
        Knowledge.created_by == ctx.user_id,
        granted,
    )


async def load_knowledge_visibility(
    db: AsyncSession, ctx: RequestContext, knowledge_id: str
) -> ResourceVisibility | None:
    """Read the visibility of one knowledge base in ``ctx``'s workspace."""

    row = (
        await db.exec(
            select(Knowledge.visibility, Knowledge.created_by).where(
                Knowledge.tenant_id == ctx.tenant_id,
                Knowledge.workspace_id == ctx.workspace_id,
                Knowledge.id == knowledge_id,
                Knowledge.deleted_at.is_(None),
            )
        )
    ).first()
    if row is None:
        return None
    return ResourceVisibility(
        visibility=str(row[0] or DEFAULT_KNOWLEDGE_VISIBILITY),
        created_by=row[1],
    )
