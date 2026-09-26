"""Which knowledge bases a workspace member can see.

``Knowledge.visibility`` decides who sees a knowledge base beyond its
workspace role ladder:

* ``private``: its creator, workspace owners and admins, and members with an
  explicit resource grant on it;
* ``workspace``: every member the role ladder admits;
* ``tenant``: as ``workspace`` in its own workspace, and readable from every
  other workspace of the tenant: listed as shared, opened, and queried by
  members who may run retrieval, but never changed there.

Single-resource access is decided by the kernel permission check with the
visibility this module resolves; listings apply the same rule in SQL. A read
from another workspace runs in the knowledge base's own workspace, under a
context that can do nothing there but read.
"""

from __future__ import annotations

import dataclasses
from typing import Any

from sqlalchemy import and_, exists, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import (
    RESOURCE_KNOWLEDGE,
    VISIBILITY_PRIVATE,
    ResourceVisibility,
    sees_private_resources,
)
from app.kernel.identity.rbac import WORKSPACE_ROLE_DEV, WORKSPACE_ROLE_VIEWER
from app.kernel.runtime.runs.content_capture import CAPTURE_METADATA_ONLY
from app.modules.identity.domain.models import ResourceGrant
from app.modules.knowledge.domain.models import Knowledge

KNOWLEDGE_VISIBILITIES = ("private", "workspace", "tenant")
DEFAULT_KNOWLEDGE_VISIBILITY = "workspace"
VISIBILITY_TENANT = "tenant"


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


def shared_knowledge_clause(ctx: RequestContext) -> Any:
    """SQL filter for the knowledge bases other workspaces share with ``ctx``'s."""

    return and_(
        Knowledge.tenant_id == ctx.tenant_id,
        Knowledge.workspace_id != ctx.workspace_id,
        Knowledge.visibility == VISIBILITY_TENANT,
        Knowledge.deleted_at.is_(None),
    )


async def shared_knowledge_home(
    db: AsyncSession, ctx: RequestContext, knowledge_id: str
) -> str | None:
    """The workspace a knowledge base shared with ``ctx``'s tenant lives in.

    None when it is not shared with the tenant, or is in ``ctx``'s own
    workspace, where the ordinary rules apply.
    """

    row = (
        await db.exec(
            select(Knowledge.workspace_id).where(
                Knowledge.id == knowledge_id,
                shared_knowledge_clause(ctx),
            )
        )
    ).first()
    if row is None:
        return None
    return str(row[0])


def shared_reader_context(ctx: RequestContext, home_workspace_id: str) -> RequestContext:
    """A context for reading a shared knowledge base in its own workspace.

    A tenant-wide share lets a reader do what reading takes and no more: a
    member who may run retrieval at home (a Dev or above) queries it as a Dev
    there, anyone else only opens it, and no one carries admin authority
    across. The context is handed only to the routes that open, list and
    query one knowledge base. The run a query records lands in the home
    workspace, where the owners of the data see who read it; it keeps no
    content if the reader's own workspace keeps none.
    """

    retrieves = ctx.is_workspace_dev()
    scopes = frozenset({"read", "write"}) if retrieves else frozenset({"read"})
    if ctx.scopes is not None:
        scopes &= ctx.scopes
    return dataclasses.replace(
        ctx,
        workspace_id=home_workspace_id,
        tenant_role=None,
        workspace_role=WORKSPACE_ROLE_DEV if retrieves else WORKSPACE_ROLE_VIEWER,
        scopes=scopes,
        content_capture=(
            CAPTURE_METADATA_ONLY if ctx.content_capture == CAPTURE_METADATA_ONLY else None
        ),
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
