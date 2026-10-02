"""Which documents named in a stored copy a reader may not read now.

Registered with the kernel's knowledge redaction, which filters citations,
query results and retrieved documents kept in runs, responses and threads.
A document is unreadable when its knowledge base is private to others or not
shared with the reader's workspace, or when it is restricted and the reader is
not among its readers. A document or knowledge base that no longer exists has
nothing left to enforce, and its copies pass: deleting is not restricting.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from sqlalchemy import and_, select

from app.infra.db.session import get_async_session_local
from app.kernel.contracts.context import RequestContext
from app.kernel.identity.permissions import get_resource_grant_provider
from app.kernel.runtime.runs.knowledge_redaction import DocumentRef
from app.modules.knowledge.application.document_access import DocumentAccess
from app.modules.knowledge.domain.models import Knowledge, KnowledgeDocument


def _home_context(ctx: RequestContext, knowledge: Knowledge) -> RequestContext:
    """The reader as seen from the knowledge base's own workspace.

    A base shared from another workspace keeps its restrictions and grants
    there, and the reader holds no role in it.
    """
    if knowledge.workspace_id == ctx.workspace_id:
        return ctx
    return replace(ctx, workspace_id=knowledge.workspace_id, tenant_role=None, workspace_role="Viewer")


async def _sees_private_base(ctx: RequestContext, knowledge: Knowledge) -> bool:
    if ctx.can_govern() or (knowledge.created_by and knowledge.created_by == ctx.user_id):
        return True
    provider = get_resource_grant_provider()
    if provider is None:
        return False
    return await provider.allows_resource_action(
        ctx=ctx, resource_type="knowledge", resource_id=knowledge.id, action="read", effective_action="read"
    )


class KnowledgeDocumentReadFilter:
    async def unreadable(
        self,
        db: Any,
        ctx: RequestContext,
        refs: set[DocumentRef],
        document_ids: set[str],
    ) -> tuple[set[DocumentRef], set[str]]:
        session = db if db is not None else get_async_session_local()()
        try:
            return await self._unreadable(session, ctx, refs, document_ids)
        finally:
            if db is None:
                await session.close()

    async def _unreadable(
        self,
        session: Any,
        ctx: RequestContext,
        refs: set[DocumentRef],
        document_ids: set[str],
    ) -> tuple[set[DocumentRef], set[str]]:
        ref_of_id: dict[str, DocumentRef] = {}
        if document_ids:
            rows = (
                await session.exec(
                    select(KnowledgeDocument.id, KnowledgeDocument.knowledge_id, KnowledgeDocument.doc_key).where(
                        and_(
                            KnowledgeDocument.tenant_id == ctx.tenant_id,
                            KnowledgeDocument.id.in_(sorted(document_ids)),
                        )
                    )
                )
            ).all()
            ref_of_id = {str(row[0]): (str(row[1]), str(row[2])) for row in rows}

        keys_by_base: dict[str, set[str]] = defaultdict(set)
        for knowledge_id, doc_key in refs | set(ref_of_id.values()):
            keys_by_base[knowledge_id].add(doc_key)

        denied_by_base: dict[str, set[str]] = {}
        for knowledge_id, doc_keys in keys_by_base.items():
            knowledge = (
                await session.exec(
                    select(Knowledge).where(and_(Knowledge.tenant_id == ctx.tenant_id, Knowledge.id == knowledge_id))
                )
            ).scalars().first()
            if knowledge is None:
                continue
            home = _home_context(ctx, knowledge)
            if knowledge.visibility == "private" and not await _sees_private_base(home, knowledge):
                denied_by_base[knowledge_id] = set(doc_keys)
                continue
            if knowledge.visibility != "tenant" and knowledge.workspace_id != ctx.workspace_id:
                # Not shared with the reader's workspace at all.
                denied_by_base[knowledge_id] = set(doc_keys)
                continue
            denied_by_base[knowledge_id] = set(await DocumentAccess(session, home).denied_doc_keys(knowledge)) & doc_keys

        denied_refs = {ref for ref in refs if ref[1] in denied_by_base.get(ref[0], set())}
        denied_ids = {
            document_id
            for document_id, (knowledge_id, doc_key) in ref_of_id.items()
            if doc_key in denied_by_base.get(knowledge_id, set())
        }
        return denied_refs, denied_ids
