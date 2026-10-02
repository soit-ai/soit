"""Which documents of a knowledge base a caller may read.

A knowledge base is readable as a whole by whoever its visibility admits. A
document in it can be restricted further: a restricted document is readable
only by the workspace's Owners and Admins, the knowledge base's creator, and
members or service principals holding a ``knowledge_document`` grant with the
``read`` action on it. A restriction names a document by its key, so it holds
for every version: a sync that brings a new version and a rollback to an old
one keep it.

Every path that returns a document or its content asks here: the document
listings, the document, its content, download, chunks and versions, and
retrieval, which leaves restricted documents out before ranking, reranking or
the keyword fallback ever see them.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, select

from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import get_resource_grant_provider
from app.modules.knowledge.domain.models import KnowledgeDocumentRestriction

RESOURCE_KNOWLEDGE_DOCUMENT = "knowledge_document"


def document_resource_id(knowledge_id: str, doc_key: str) -> str:
    """The resource id a ``knowledge_document`` grant names."""
    return f"{knowledge_id}:{doc_key}"


class DocumentAccess:
    """Document restrictions of the caller's workspace, read on the caller's session."""

    def __init__(self, db: Any, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def restricted_doc_keys(self, knowledge_id: str) -> set[str]:
        query = select(KnowledgeDocumentRestriction.doc_key).where(
            and_(
                KnowledgeDocumentRestriction.tenant_id == self.ctx.tenant_id,
                KnowledgeDocumentRestriction.workspace_id == self.ctx.workspace_id,
                KnowledgeDocumentRestriction.knowledge_id == knowledge_id,
            )
        )
        return {str(key) for key in (await self.db.exec(query)).scalars().all()}

    async def is_restricted(self, knowledge_id: str, doc_key: str) -> bool:
        return doc_key in await self.restricted_doc_keys(knowledge_id)

    def sees_every_document(self, knowledge: Any) -> bool:
        """Workspace Owners and Admins, and the knowledge base's creator."""
        if self.ctx.can_govern():
            return True
        creator = getattr(knowledge, "created_by", None)
        return bool(creator) and creator == self.ctx.user_id

    async def _granted(self, knowledge_id: str, doc_key: str) -> bool:
        provider = get_resource_grant_provider()
        if provider is None:
            return False
        return await provider.allows_resource_action(
            ctx=self.ctx,
            resource_type=RESOURCE_KNOWLEDGE_DOCUMENT,
            resource_id=document_resource_id(knowledge_id, doc_key),
            action="read",
            effective_action="read",
        )

    async def denied_doc_keys(self, knowledge: Any) -> frozenset[str]:
        """The restricted documents of ``knowledge`` the caller may not read."""
        restricted = await self.restricted_doc_keys(knowledge.id)
        if not restricted or self.sees_every_document(knowledge):
            return frozenset()
        return frozenset([key for key in sorted(restricted) if not await self._granted(knowledge.id, key)])

    async def may_read(self, knowledge: Any, doc_key: str) -> bool:
        if self.sees_every_document(knowledge):
            return True
        if not await self.is_restricted(knowledge.id, doc_key):
            return True
        return await self._granted(knowledge.id, doc_key)
