"""Repositories for Responses API resource/projection persistence."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.kernel.commons.errors import NotFoundError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.responses.models import Response, ResponseEvent


class ResponseRepository:
    """Scope-aware repository for response resources."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def create(self, response: Response) -> Response:
        response.tenant_id = self.ctx.tenant_id
        response.workspace_id = self.ctx.workspace_id
        response.created_by = self.ctx.user_id
        response.updated_by = self.ctx.user_id
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)
        return response

    def get(self, response_id: str) -> Optional[Response]:
        query = select(Response).where(
            and_(
                Response.id == response_id,
                Response.tenant_id == self.ctx.tenant_id,
                Response.workspace_id == self.ctx.workspace_id,
            )
        )
        result = self.db.exec(query).first()
        return result if isinstance(result, Response) else result[0] if result else None

    def require(self, response_id: str) -> Response:
        response = self.get(response_id)
        if not response:
            raise NotFoundError(f"Response not found: {response_id}")
        return response

    def update(self, response: Response) -> Response:
        response.updated_at = utc_now()
        response.updated_by = self.ctx.user_id
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)
        return response

    def list_for_run(self, run_id: str) -> list[Response]:
        query = (
            select(Response)
            .where(
                and_(
                    Response.run_id == run_id,
                    Response.tenant_id == self.ctx.tenant_id,
                    Response.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(Response.created_at.asc(), Response.id.asc())
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, Response) else item[0] for item in results]


class ResponseEventRepository:
    """Repository for persisted response semantic events."""

    def __init__(self, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def next_sequence(self, response_id: str) -> int:
        query = select(func.max(ResponseEvent.sequence)).where(
            and_(
                ResponseEvent.response_id == response_id,
                ResponseEvent.tenant_id == self.ctx.tenant_id,
                ResponseEvent.workspace_id == self.ctx.workspace_id,
            )
        )
        value = self.db.exec(query).first()
        if hasattr(value, "__getitem__"):
            current = value[0]
        else:
            current = value
        return int(current or 0) + 1

    def create(self, event: ResponseEvent) -> ResponseEvent:
        event.tenant_id = self.ctx.tenant_id
        event.workspace_id = self.ctx.workspace_id
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_for_response(self, response_id: str, *, limit: int, offset: int) -> list[ResponseEvent]:
        query = (
            select(ResponseEvent)
            .where(
                and_(
                    ResponseEvent.response_id == response_id,
                    ResponseEvent.tenant_id == self.ctx.tenant_id,
                    ResponseEvent.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(ResponseEvent.sequence.asc(), ResponseEvent.created_at.asc(), ResponseEvent.id.asc())
            .offset(offset)
            .limit(limit)
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, ResponseEvent) else item[0] for item in results]

    def list_for_run(self, run_id: str) -> list[ResponseEvent]:
        query = (
            select(ResponseEvent)
            .where(
                and_(
                    ResponseEvent.run_id == run_id,
                    ResponseEvent.tenant_id == self.ctx.tenant_id,
                    ResponseEvent.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(
                ResponseEvent.created_at.asc(),
                ResponseEvent.sequence.asc(),
                ResponseEvent.id.asc(),
            )
        )
        results = list(self.db.exec(query).all())
        return [item if isinstance(item, ResponseEvent) else item[0] for item in results]
