"""Cross-domain model reference lookup adapter."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.threads import Thread
from app.modules.agent.domain.models import Agent, AgentBinding, AgentVersion
from app.modules.knowledge.domain.models import Knowledge, KnowledgeIndex
from app.modules.workflow.domain.models import WorkflowVersion


def _contains_model_ref(value: Any, model_ref: str) -> bool:
    if isinstance(value, dict):
        return any(_contains_model_ref(item, model_ref) for item in value.values())
    if isinstance(value, list):
        return any(_contains_model_ref(item, model_ref) for item in value)
    return value == model_ref


class DatabaseModelReferenceUsage:
    """Inspect active scoped configuration before deleting a provider model."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def _scoped(self, model, *clauses):
        return select(model).where(
            model.tenant_id == self.ctx.tenant_id,
            model.workspace_id == self.ctx.workspace_id,
            *clauses,
        )

    def list_references(self, model_ref: str) -> list[dict[str, str]]:
        references: list[dict[str, str]] = []

        agents = self.db.execute(
            self._scoped(
                Agent,
                Agent.deleted_at.is_(None),
                Agent.default_model_ref == model_ref,
            ).limit(20)
        ).scalars()
        references.extend({"type": "agent", "id": item.id} for item in agents)

        bindings = self.db.execute(
            self._scoped(
                AgentBinding,
                AgentBinding.binding_type == "model",
                or_(
                    AgentBinding.target_key == model_ref,
                    AgentBinding.target_id == model_ref,
                ),
            ).limit(20)
        ).scalars()
        references.extend({"type": "agent_binding", "id": item.id} for item in bindings)

        threads = self.db.execute(
            self._scoped(
                Thread,
                Thread.deleted_at.is_(None),
                Thread.default_model_ref == model_ref,
            ).limit(20)
        ).scalars()
        references.extend({"type": "thread", "id": item.id} for item in threads)

        knowledge = self.db.execute(
            self._scoped(
                Knowledge,
                or_(
                    Knowledge.default_embedding_model_ref == model_ref,
                    Knowledge.default_reranker_ref == model_ref,
                ),
            ).limit(20)
        ).scalars()
        references.extend({"type": "knowledge", "id": item.id} for item in knowledge)

        indexes = self.db.execute(
            self._scoped(
                KnowledgeIndex,
                or_(
                    KnowledgeIndex.embedding_model_ref == model_ref,
                    KnowledgeIndex.reranker_ref == model_ref,
                ),
            ).limit(20)
        ).scalars()
        references.extend({"type": "knowledge_index", "id": item.id} for item in indexes)

        agent_versions = self.db.execute(
            self._scoped(AgentVersion, AgentVersion.status == "published").limit(500)
        ).scalars()
        references.extend(
            {"type": "agent_version", "id": item.id}
            for item in agent_versions
            if _contains_model_ref(item.spec_json, model_ref)
        )

        workflow_versions = self.db.execute(
            self._scoped(
                WorkflowVersion,
                WorkflowVersion.status == "published",
            ).limit(500)
        ).scalars()
        references.extend(
            {"type": "workflow_version", "id": item.id}
            for item in workflow_versions
            if _contains_model_ref(item.spec_json, model_ref)
        )
        return references[:100]
