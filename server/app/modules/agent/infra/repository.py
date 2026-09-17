"""Agent repositories backed by the new Agent tables."""

from __future__ import annotations

from sqlalchemy import and_, desc, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.modules.agent.domain.models import (
    Agent,
    AgentBinding,
    AgentPublish,
    AgentVersion,
)


def _scalar(value):
    if hasattr(value, "_mapping"):
        return value[0]
    if isinstance(value, tuple):
        return value[0]
    return value


class AgentRepository:
    """Repository for Agent aggregate operations."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, agent: Agent) -> Agent:
        agent.tenant_id = self.ctx.tenant_id
        agent.workspace_id = self.ctx.workspace_id
        agent.created_by = self.ctx.user_id
        agent.updated_by = self.ctx.user_id
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def get_by_id(self, agent_id: str) -> Agent | None:
        query = select(Agent).where(
            and_(
                Agent.id == agent_id,
                Agent.tenant_id == self.ctx.tenant_id,
                Agent.workspace_id == self.ctx.workspace_id,
                Agent.deleted_at.is_(None),
            )
        )
        return (await self.db.exec(query)).scalars().first()

    async def get_by_name(self, name: str) -> Agent | None:
        query = select(Agent).where(
            and_(
                Agent.name == name,
                Agent.tenant_id == self.ctx.tenant_id,
                Agent.workspace_id == self.ctx.workspace_id,
                Agent.deleted_at.is_(None),
            )
        )
        return (await self.db.exec(query)).scalars().first()

    async def list(self, limit: int = 20, offset: int = 0) -> list[Agent]:
        query = (
            select(Agent)
            .where(
                and_(
                    Agent.tenant_id == self.ctx.tenant_id,
                    Agent.workspace_id == self.ctx.workspace_id,
                    Agent.deleted_at.is_(None),
                )
            )
            .order_by(desc(Agent.updated_at))
            .offset(offset)
            .limit(limit)
        )
        return list((await self.db.exec(query)).scalars().all())

    async def update(self, agent: Agent) -> Agent:
        agent.updated_at = utc_now()
        agent.updated_by = self.ctx.user_id
        self.db.add(agent)
        await self.db.commit()
        await self.db.refresh(agent)
        return agent

    async def next_version_number(self, agent_id: str) -> int:
        query = select(func.max(AgentVersion.version)).where(
            and_(
                AgentVersion.agent_id == agent_id,
                AgentVersion.tenant_id == self.ctx.tenant_id,
                AgentVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        max_value = _scalar((await self.db.exec(query)).one())
        return int(max_value or 0) + 1


class AgentVersionRepository:
    """Repository for AgentVersion snapshots."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, version: AgentVersion) -> AgentVersion:
        version.tenant_id = self.ctx.tenant_id
        version.workspace_id = self.ctx.workspace_id
        version.created_by = self.ctx.user_id
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def get_by_id(self, version_id: str) -> AgentVersion | None:
        query = select(AgentVersion).where(
            and_(
                AgentVersion.id == version_id,
                AgentVersion.tenant_id == self.ctx.tenant_id,
                AgentVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        return (await self.db.exec(query)).scalars().first()

    async def list_by_agent(self, agent_id: str, *, limit: int = 20, offset: int = 0) -> list[AgentVersion]:
        query = (
            select(AgentVersion)
            .where(
                and_(
                    AgentVersion.agent_id == agent_id,
                    AgentVersion.tenant_id == self.ctx.tenant_id,
                    AgentVersion.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(AgentVersion.version), desc(AgentVersion.created_at))
            .offset(offset)
            .limit(limit)
        )
        return list((await self.db.exec(query)).scalars().all())

    async def list_awaiting_review(self, *, limit: int = 20) -> list[AgentVersion]:
        """Drafts somebody is waiting on, oldest wait first.

        Oldest first because the useful question is which one has been sitting
        longest, not which was asked most recently.
        """
        query = (
            select(AgentVersion)
            .where(
                and_(
                    AgentVersion.tenant_id == self.ctx.tenant_id,
                    AgentVersion.workspace_id == self.ctx.workspace_id,
                    AgentVersion.review_status.in_(("in_review", "changes_requested")),
                )
            )
            .order_by(AgentVersion.review_requested_at)
            .limit(limit)
        )
        return list((await self.db.exec(query)).scalars().all())

    async def update(self, version: AgentVersion) -> AgentVersion:
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version


class AgentBindingRepository:
    """Repository for Agent bindings."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, binding: AgentBinding) -> AgentBinding:
        binding.tenant_id = self.ctx.tenant_id
        binding.workspace_id = self.ctx.workspace_id
        self.db.add(binding)
        await self.db.commit()
        await self.db.refresh(binding)
        return binding

    async def create_many(self, bindings: list[AgentBinding]) -> list[AgentBinding]:
        for binding in bindings:
            binding.tenant_id = self.ctx.tenant_id
            binding.workspace_id = self.ctx.workspace_id
        self.db.add_all(bindings)
        await self.db.commit()
        for binding in bindings:
            await self.db.refresh(binding)
        return bindings

    async def list_for_version(self, agent_version_id: str) -> list[AgentBinding]:
        query = (
            select(AgentBinding)
            .where(
                and_(
                    AgentBinding.agent_version_id == agent_version_id,
                    AgentBinding.tenant_id == self.ctx.tenant_id,
                    AgentBinding.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(AgentBinding.sort_order.asc(), AgentBinding.created_at.asc())
        )
        return list((await self.db.exec(query)).scalars().all())


class AgentPublishRepository:
    """Repository for Agent publish records."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def create(self, publish: AgentPublish) -> AgentPublish:
        publish.tenant_id = self.ctx.tenant_id
        publish.workspace_id = self.ctx.workspace_id
        publish.created_by = self.ctx.user_id
        query = select(func.max(AgentPublish.sequence)).where(
            and_(
                AgentPublish.agent_id == publish.agent_id,
                AgentPublish.tenant_id == self.ctx.tenant_id,
                AgentPublish.workspace_id == self.ctx.workspace_id,
            )
        )
        max_value = _scalar((await self.db.exec(query)).one())
        publish.sequence = int(max_value or 0) + 1
        self.db.add(publish)
        await self.db.commit()
        await self.db.refresh(publish)
        return publish

    async def list_by_agent(self, agent_id: str) -> list[AgentPublish]:
        query = (
            select(AgentPublish)
            .where(
                and_(
                    AgentPublish.agent_id == agent_id,
                    AgentPublish.tenant_id == self.ctx.tenant_id,
                    AgentPublish.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(AgentPublish.sequence))
        )
        return list((await self.db.exec(query)).scalars().all())
