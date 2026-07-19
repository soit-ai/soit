"""Workspace-scoped aggregate search queries."""

from collections.abc import Callable
from urllib.parse import quote

from sqlalchemy import desc, or_
from sqlmodel import Session, select

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run
from app.kernel.runtime.db.models.threads import Thread
from app.modules.agent.domain.models import Agent
from app.modules.knowledge.domain.models import Knowledge
from app.modules.modelhub.domain.models import ProviderModel
from app.modules.plugin.domain.models import Plugin
from app.modules.search.application.schemas import (
    GlobalSearchResponse,
    GlobalSearchResult,
    SearchKind,
)
from app.modules.workflow.domain.models import Workflow

SEARCH_KINDS: tuple[SearchKind, ...] = (
    "agent",
    "workflow",
    "knowledge",
    "plugin",
    "model",
    "thread",
    "run",
)


def _literal_like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _summary(*values: str | None) -> str | None:
    return next((value.strip() for value in values if value and value.strip()), None)


class GlobalSearchService:
    """Search user-facing resources in the current workspace."""

    def __init__(self, *, db: Session, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    def search(
        self,
        *,
        query_text: str,
        kinds: list[SearchKind] | None,
        limit: int,
    ) -> GlobalSearchResponse:
        normalized = query_text.strip()
        pattern = _literal_like_pattern(normalized)
        requested = tuple(dict.fromkeys(kinds or SEARCH_KINDS))
        handlers: dict[
            SearchKind,
            Callable[[str, int, str], list[GlobalSearchResult]],
        ] = {
            "agent": self._search_agents,
            "workflow": self._search_workflows,
            "knowledge": self._search_knowledge,
            "plugin": self._search_plugins,
            "model": self._search_models,
            "thread": self._search_threads,
            "run": self._search_runs,
        }
        items: list[GlobalSearchResult] = []
        counts: dict[SearchKind, int] = {}
        for kind in requested:
            matches = handlers[kind](pattern, limit, normalized)
            items.extend(matches)
            counts[kind] = len(matches)
        return GlobalSearchResponse(query=normalized, items=items, counts=counts)

    def _rank(
        self,
        items: list[GlobalSearchResult],
        query_text: str,
        limit: int,
    ) -> list[GlobalSearchResult]:
        needle = query_text.casefold()

        def score(item: GlobalSearchResult) -> tuple[int, float, str]:
            title = item.title.casefold()
            identifier = item.id.casefold()
            subtitle = (item.subtitle or "").casefold()
            if needle == title or needle == identifier:
                relevance = 0
            elif title.startswith(needle):
                relevance = 1
            elif identifier.startswith(needle):
                relevance = 2
            elif needle in title:
                relevance = 3
            elif needle in identifier:
                relevance = 4
            elif needle in subtitle:
                relevance = 5
            else:
                relevance = 6
            timestamp = item.updated_at.timestamp() if item.updated_at else 0.0
            return relevance, -timestamp, title

        return sorted(items, key=score)[:limit]

    @staticmethod
    def _fetch_limit(limit: int) -> int:
        return max(20, limit * 4)

    def _search_agents(self, pattern: str, limit: int, query_text: str) -> list[GlobalSearchResult]:
        rows = self.db.exec(
            select(Agent)
            .where(
                Agent.tenant_id == self.ctx.tenant_id,
                Agent.workspace_id == self.ctx.workspace_id,
                Agent.deleted_at.is_(None),
                or_(
                    Agent.id.ilike(pattern, escape="\\"),
                    Agent.name.ilike(pattern, escape="\\"),
                    Agent.description.ilike(pattern, escape="\\"),
                    Agent.category.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(desc(Agent.updated_at))
            .limit(self._fetch_limit(limit))
        ).all()
        return self._rank(
            [
                GlobalSearchResult(
                    kind="agent",
                    id=row.id,
                    title=row.name,
                    subtitle=_summary(row.description, row.category),
                    status=row.status,
                    url=f"/agents/{row.id}",
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            query_text,
            limit,
        )

    def _search_workflows(self, pattern: str, limit: int, query_text: str) -> list[GlobalSearchResult]:
        rows = self.db.exec(
            select(Workflow)
            .where(
                Workflow.tenant_id == self.ctx.tenant_id,
                Workflow.workspace_id == self.ctx.workspace_id,
                Workflow.deleted_at.is_(None),
                or_(
                    Workflow.id.ilike(pattern, escape="\\"),
                    Workflow.name.ilike(pattern, escape="\\"),
                    Workflow.description.ilike(pattern, escape="\\"),
                    Workflow.summary.ilike(pattern, escape="\\"),
                    Workflow.category.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(desc(Workflow.updated_at))
            .limit(self._fetch_limit(limit))
        ).all()
        return self._rank(
            [
                GlobalSearchResult(
                    kind="workflow",
                    id=row.id,
                    title=row.name,
                    subtitle=_summary(row.description, row.summary, row.category),
                    status=row.status,
                    url=f"/workflow/{row.id}/build",
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            query_text,
            limit,
        )

    def _search_knowledge(self, pattern: str, limit: int, query_text: str) -> list[GlobalSearchResult]:
        rows = self.db.exec(
            select(Knowledge)
            .where(
                Knowledge.tenant_id == self.ctx.tenant_id,
                Knowledge.workspace_id == self.ctx.workspace_id,
                Knowledge.deleted_at.is_(None),
                or_(
                    Knowledge.id.ilike(pattern, escape="\\"),
                    Knowledge.name.ilike(pattern, escape="\\"),
                    Knowledge.description.ilike(pattern, escape="\\"),
                    Knowledge.type.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(desc(Knowledge.updated_at))
            .limit(self._fetch_limit(limit))
        ).all()
        return self._rank(
            [
                GlobalSearchResult(
                    kind="knowledge",
                    id=row.id,
                    title=row.name,
                    subtitle=_summary(row.description, row.type),
                    status=row.status,
                    url=f"/knowledge/{row.id}",
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            query_text,
            limit,
        )

    def _search_plugins(self, pattern: str, limit: int, query_text: str) -> list[GlobalSearchResult]:
        rows = self.db.exec(
            select(Plugin)
            .where(
                Plugin.tenant_id == self.ctx.tenant_id,
                Plugin.workspace_id == self.ctx.workspace_id,
                or_(
                    Plugin.id.ilike(pattern, escape="\\"),
                    Plugin.name.ilike(pattern, escape="\\"),
                    Plugin.description.ilike(pattern, escape="\\"),
                    Plugin.publisher.ilike(pattern, escape="\\"),
                    Plugin.version.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(desc(Plugin.updated_at))
            .limit(self._fetch_limit(limit))
        ).all()
        return self._rank(
            [
                GlobalSearchResult(
                    kind="plugin",
                    id=row.id,
                    title=row.name,
                    subtitle=_summary(row.description, f"{row.publisher} · {row.version}"),
                    status=row.status,
                    url=f"/plugins?q={quote(row.name)}",
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            query_text,
            limit,
        )

    def _search_models(self, pattern: str, limit: int, query_text: str) -> list[GlobalSearchResult]:
        rows = self.db.exec(
            select(ProviderModel)
            .where(
                ProviderModel.tenant_id == self.ctx.tenant_id,
                ProviderModel.workspace_id == self.ctx.workspace_id,
                or_(
                    ProviderModel.id.ilike(pattern, escape="\\"),
                    ProviderModel.model_id.ilike(pattern, escape="\\"),
                    ProviderModel.display_name.ilike(pattern, escape="\\"),
                    ProviderModel.description.ilike(pattern, escape="\\"),
                    ProviderModel.provider_kind.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(desc(ProviderModel.updated_at))
            .limit(self._fetch_limit(limit))
        ).all()
        return self._rank(
            [
                GlobalSearchResult(
                    kind="model",
                    id=row.id,
                    title=row.display_name or row.model_id,
                    subtitle=_summary(row.description, f"{row.provider_kind}/{row.model_id}"),
                    status=row.status,
                    url=f"/models/library?keyword={quote(row.model_id)}",
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            query_text,
            limit,
        )

    def _search_threads(self, pattern: str, limit: int, query_text: str) -> list[GlobalSearchResult]:
        rows = self.db.exec(
            select(Thread)
            .where(
                Thread.tenant_id == self.ctx.tenant_id,
                Thread.workspace_id == self.ctx.workspace_id,
                Thread.deleted_at.is_(None),
                or_(
                    Thread.id.ilike(pattern, escape="\\"),
                    Thread.title.ilike(pattern, escape="\\"),
                    Thread.summary.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(desc(Thread.updated_at))
            .limit(self._fetch_limit(limit))
        ).all()
        return self._rank(
            [
                GlobalSearchResult(
                    kind="thread",
                    id=row.id,
                    title=row.title or row.id,
                    subtitle=_summary(row.summary, row.agent_id),
                    status=row.status,
                    url=f"/chat/{row.agent_id or 'default'}/{row.id}",
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            query_text,
            limit,
        )

    def _search_runs(self, pattern: str, limit: int, query_text: str) -> list[GlobalSearchResult]:
        rows = self.db.exec(
            select(Run)
            .where(
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
                or_(
                    Run.id.ilike(pattern, escape="\\"),
                    Run.subject_id.ilike(pattern, escape="\\"),
                    Run.input_summary.ilike(pattern, escape="\\"),
                    Run.output_summary.ilike(pattern, escape="\\"),
                    Run.error_message.ilike(pattern, escape="\\"),
                ),
            )
            .order_by(desc(Run.updated_at))
            .limit(self._fetch_limit(limit))
        ).all()
        return self._rank(
            [
                GlobalSearchResult(
                    kind="run",
                    id=row.id,
                    title=row.id,
                    subtitle=_summary(
                        row.input_summary,
                        row.output_summary,
                        row.error_message,
                        " · ".join(value for value in (row.subject_kind, row.subject_id) if value),
                    ),
                    status=row.status,
                    url=f"/observe/runs/{row.id}",
                    updated_at=row.updated_at,
                )
                for row in rows
            ],
            query_text,
            limit,
        )
