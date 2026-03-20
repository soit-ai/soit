"""Agent repositories backed by the new Agent tables."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.time import utc_now
from app.modules.agent.domain.models import Agent, AgentBinding, AgentPublish, AgentVersion


class AgentRepository:
    """Repository for Agent aggregate operations."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, agent: Agent) -> Agent:
        agent.tenant_id = self.ctx.tenant_id
        agent.workspace_id = self.ctx.workspace_id
        agent.created_by = self.ctx.user_id
        agent.updated_by = self.ctx.user_id
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_by_id(self, agent_id: str) -> Optional[Agent]:
        query = select(Agent).where(
            and_(
                Agent.id == agent_id,
                Agent.tenant_id == self.ctx.tenant_id,
                Agent.workspace_id == self.ctx.workspace_id,
                Agent.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, Agent) else result[0] if result else None

    def get_by_name(self, name: str) -> Optional[Agent]:
        query = select(Agent).where(
            and_(
                Agent.name == name,
                Agent.tenant_id == self.ctx.tenant_id,
                Agent.workspace_id == self.ctx.workspace_id,
                Agent.deleted_at.is_(None),
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, Agent) else result[0] if result else None

    def list(self, limit: int = 20, offset: int = 0) -> list[Agent]:
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
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Agent) else item[0] for item in results]

    def update(self, agent: Agent) -> Agent:
        agent.updated_at = utc_now()
        agent.updated_by = self.ctx.user_id
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def next_version_number(self, agent_id: str) -> int:
        query = select(func.max(AgentVersion.version)).where(
            and_(
                AgentVersion.agent_id == agent_id,
                AgentVersion.tenant_id == self.ctx.tenant_id,
                AgentVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        max_value = self.db.exec(query).one()
        if hasattr(max_value, "_mapping"):
            max_value = max_value[0]
        elif isinstance(max_value, tuple):
            max_value = max_value[0]
        return int(max_value or 0) + 1


class AgentVersionRepository:
    """Repository for AgentVersion snapshots."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, version: AgentVersion) -> AgentVersion:
        version.tenant_id = self.ctx.tenant_id
        version.workspace_id = self.ctx.workspace_id
        version.created_by = self.ctx.user_id
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version

    def get_by_id(self, version_id: str) -> Optional[AgentVersion]:
        query = select(AgentVersion).where(
            and_(
                AgentVersion.id == version_id,
                AgentVersion.tenant_id == self.ctx.tenant_id,
                AgentVersion.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, AgentVersion) else result[0] if result else None

    def list_by_agent(self, agent_id: str, *, limit: int = 20, offset: int = 0) -> list[AgentVersion]:
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
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AgentVersion) else item[0] for item in results]

    def update(self, version: AgentVersion) -> AgentVersion:
        self.db.add(version)
        self.db.commit()
        self.db.refresh(version)
        return version


class AgentBindingRepository:
    """Repository for Agent bindings."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, binding: AgentBinding) -> AgentBinding:
        binding.tenant_id = self.ctx.tenant_id
        binding.workspace_id = self.ctx.workspace_id
        self.db.add(binding)
        self.db.commit()
        self.db.refresh(binding)
        return binding

    def list_for_version(self, agent_version_id: str) -> list[AgentBinding]:
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
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AgentBinding) else item[0] for item in results]


class AgentPublishRepository:
    """Repository for Agent publish records."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, publish: AgentPublish) -> AgentPublish:
        publish.tenant_id = self.ctx.tenant_id
        publish.workspace_id = self.ctx.workspace_id
        publish.created_by = self.ctx.user_id
        self.db.add(publish)
        self.db.commit()
        self.db.refresh(publish)
        return publish

    def list_by_agent(self, agent_id: str) -> list[AgentPublish]:
        query = (
            select(AgentPublish)
            .where(
                and_(
                    AgentPublish.agent_id == agent_id,
                    AgentPublish.tenant_id == self.ctx.tenant_id,
                    AgentPublish.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(desc(AgentPublish.created_at))
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, AgentPublish) else item[0] for item in results]
