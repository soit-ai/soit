"""Workflow repositories."""

from __future__ import annotations

from sqlalchemy import and_, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.modules.workflow.domain.models import (
    Workflow,
    WorkflowPublish,
    WorkflowVersion,
)


class WorkflowRepository:
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, workflow: Workflow) -> Workflow:
        workflow.tenant_id = self.ctx.tenant_id
        workflow.workspace_id = self.ctx.workspace_id
        workflow.created_by = workflow.created_by or self.ctx.user_id
        workflow.updated_by = workflow.updated_by or self.ctx.user_id
        self.db.add(workflow)
        await self.db.commit()
        return workflow

    async def update(self, workflow: Workflow) -> Workflow:
        workflow.updated_at = utc_now()
        workflow.updated_by = self.ctx.user_id
        self.db.add(workflow)
        await self.db.commit()
        return workflow

    async def get_by_id(self, workflow_id: str) -> Workflow | None:
        query = select(Workflow).where(
            and_(
                Workflow.id == workflow_id,
                Workflow.tenant_id == self.ctx.tenant_id,
                Workflow.workspace_id == self.ctx.workspace_id,
                Workflow.deleted_at.is_(None),
            )
        )
        return (await self.db.execute(query)).scalars().first()

    async def get_by_name(self, name: str) -> Workflow | None:
        query = select(Workflow).where(
            and_(
                Workflow.name == name,
                Workflow.tenant_id == self.ctx.tenant_id,
                Workflow.workspace_id == self.ctx.workspace_id,
                Workflow.deleted_at.is_(None),
            )
        )
        return (await self.db.execute(query)).scalars().first()

    async def list(self, *, limit: int, offset: int) -> list[Workflow]:
        query = (
            select(Workflow)
            .where(
                and_(
                    Workflow.tenant_id == self.ctx.tenant_id,
                    Workflow.workspace_id == self.ctx.workspace_id,
                    Workflow.deleted_at.is_(None),
                    Workflow.status != "archived",
                )
            )
            .order_by(desc(Workflow.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(query)).scalars().all())

    async def next_version_number(self, workflow_id: str) -> int:
        query = select(func.max(WorkflowVersion.version)).where(
            and_(
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.tenant_id == self.ctx.tenant_id,
                WorkflowVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        max_val = (await self.db.execute(query)).scalar_one_or_none()
        return int(max_val or 0) + 1


class WorkflowVersionRepository:
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, version: WorkflowVersion) -> WorkflowVersion:
        version.tenant_id = self.ctx.tenant_id
        version.workspace_id = self.ctx.workspace_id
        version.created_by = version.created_by or self.ctx.user_id
        self.db.add(version)
        await self.db.commit()
        return version

    async def update(self, version: WorkflowVersion) -> WorkflowVersion:
        self.db.add(version)
        await self.db.commit()
        return version

    async def get_by_id(self, version_id: str) -> WorkflowVersion | None:
        query = select(WorkflowVersion).where(
            and_(
                WorkflowVersion.id == version_id,
                WorkflowVersion.tenant_id == self.ctx.tenant_id,
                WorkflowVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        return (await self.db.execute(query)).scalars().first()

    async def list_by_workflow(self, workflow_id: str, *, limit: int, offset: int) -> list[WorkflowVersion]:
        query = (
            select(WorkflowVersion)
            .where(
                and_(
                    WorkflowVersion.workflow_id == workflow_id,
                    WorkflowVersion.tenant_id == self.ctx.tenant_id,
                    WorkflowVersion.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(WorkflowVersion.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list((await self.db.execute(query)).scalars().all())


class WorkflowPublishRepository:
    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, publish: WorkflowPublish) -> WorkflowPublish:
        publish.tenant_id = self.ctx.tenant_id
        publish.workspace_id = self.ctx.workspace_id
        publish.created_by = publish.created_by or self.ctx.user_id
        self.db.add(publish)
        await self.db.commit()
        return publish

    async def list_by_workflow(self, workflow_id: str) -> list[WorkflowPublish]:
        query = (
            select(WorkflowPublish)
            .where(
                and_(
                    WorkflowPublish.workflow_id == workflow_id,
                    WorkflowPublish.tenant_id == self.ctx.tenant_id,
                    WorkflowPublish.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(WorkflowPublish.created_at))
        )
        return list((await self.db.execute(query)).scalars().all())
