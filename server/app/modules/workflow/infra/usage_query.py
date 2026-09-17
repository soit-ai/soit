"""Database implementation of the published workflow usage contract."""

from __future__ import annotations

from sqlalchemy import and_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.contracts.context import RequestContext
from app.modules.workflow.domain.models import Workflow, WorkflowVersion


class DatabasePublishedWorkflowUsagePort:
    """Return scoped published workflow specs for compatibility analysis."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def list_published_specs(self) -> list[dict]:
        version_ids = (await self.db.exec(
            select(Workflow.published_version_id).where(
                and_(
                    Workflow.tenant_id == self.ctx.tenant_id,
                    Workflow.workspace_id == self.ctx.workspace_id,
                    Workflow.published_version_id.is_not(None),
                )
            )
        )).scalars().all()
        ids = [str(value) for value in version_ids if value]
        if not ids:
            return []
        versions = (await self.db.exec(
            select(WorkflowVersion).where(
                and_(
                    WorkflowVersion.tenant_id == self.ctx.tenant_id,
                    WorkflowVersion.workspace_id == self.ctx.workspace_id,
                    WorkflowVersion.id.in_(ids),
                    WorkflowVersion.spec_schema == "workflow.v1",
                )
            )
        )).scalars().all()
        return [dict(version.spec_json or {}) for version in versions]
