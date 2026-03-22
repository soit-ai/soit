"""MCP server repository."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.modules.integrations.mcp.domain.models import MCPServer


class MCPServerRepository:
    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, server: MCPServer) -> MCPServer:
        server.tenant_id = self.ctx.tenant_id
        server.workspace_id = self.ctx.workspace_id
        server.created_by = server.created_by or self.ctx.user_id
        server.updated_by = server.updated_by or self.ctx.user_id
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        return server

    def update(self, server: MCPServer) -> MCPServer:
        server.updated_at = utc_now()
        server.updated_by = self.ctx.user_id
        self.db.add(server)
        self.db.commit()
        self.db.refresh(server)
        return server

    def get_by_id(self, server_id: str) -> Optional[MCPServer]:
        query = select(MCPServer).where(
            and_(
                MCPServer.id == server_id,
                MCPServer.tenant_id == self.ctx.tenant_id,
                MCPServer.workspace_id == self.ctx.workspace_id,
                MCPServer.deleted_at.is_(None),
            )
        )
        return self.db.execute(query).scalars().first()

    def get_by_name(self, name: str) -> Optional[MCPServer]:
        query = select(MCPServer).where(
            and_(
                MCPServer.name == name,
                MCPServer.tenant_id == self.ctx.tenant_id,
                MCPServer.workspace_id == self.ctx.workspace_id,
                MCPServer.deleted_at.is_(None),
            )
        )
        return self.db.execute(query).scalars().first()

    def list(self, *, limit: int, offset: int, enabled_only: bool = False) -> list[MCPServer]:
        filters = [
            MCPServer.tenant_id == self.ctx.tenant_id,
            MCPServer.workspace_id == self.ctx.workspace_id,
            MCPServer.deleted_at.is_(None),
            MCPServer.status != "archived",
        ]
        if enabled_only:
            filters.append(MCPServer.enabled.is_(True))
        query = (
            select(MCPServer)
            .where(and_(*filters))
            .order_by(desc(MCPServer.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(query).scalars().all())
