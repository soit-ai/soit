"""Agent-specific versioning adapter."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.kernel.commons.time import utc_now
from app.modules.agent.domain.models import AgentPublish, AgentVersion
from app.modules.agent.infra.repository import (
    AgentPublishRepository,
    AgentRepository,
    AgentVersionRepository,
)
from app.modules.versioning.application.service import VersioningAdapter


class AgentVersioningAdapter(VersioningAdapter):
    """Persist shared versioning actions onto Agent tables."""

    subject_kind = "agent"

    def __init__(
        self,
        *,
        agent_repo: AgentRepository,
        version_repo: AgentVersionRepository,
        publish_repo: AgentPublishRepository,
        sync_bindings: Callable[[Any, AgentVersion], None],
    ) -> None:
        self.agent_repo = agent_repo
        self.version_repo = version_repo
        self.publish_repo = publish_repo
        self.sync_bindings = sync_bindings

    def get_subject(self, subject_id: str) -> Any | None:
        return self.agent_repo.get_by_id(subject_id)

    def get_version(self, version_id: str) -> AgentVersion | None:
        return self.version_repo.get_by_id(version_id)

    def version_matches_subject(self, version: AgentVersion, subject_id: str) -> bool:
        return version.agent_id == subject_id

    def next_version_number(self, subject_id: str) -> int:
        return self.agent_repo.next_version_number(subject_id)

    def create_version(
        self,
        subject_id: str,
        *,
        version_no: int,
        spec_schema: str,
        spec_json: dict[str, Any],
        based_on_version_id: str | None,
        metadata: dict[str, Any] | None,
    ) -> AgentVersion:
        payload = metadata or {}
        return self.version_repo.create(
            AgentVersion(
                agent_id=subject_id,
                version=version_no,
                status="draft",
                spec_schema=spec_schema,
                spec_json=spec_json,
                checksum=payload.get("checksum"),
                created_from_version_id=based_on_version_id,
                changelog=payload.get("changelog"),
            )
        )

    def update_version(self, version: AgentVersion) -> AgentVersion:
        return self.version_repo.update(version)

    def update_head(self, subject: Any, version: AgentVersion) -> Any:
        subject.current_version_id = version.id
        if isinstance(version.spec_json, dict):
            bindings = version.spec_json.get("bindings") or {}
            model_ref = bindings.get("model_ref") if isinstance(bindings, dict) else None
            if model_ref:
                subject.default_model_ref = model_ref
        return self.agent_repo.update(subject)

    def update_live(self, subject: Any, version: AgentVersion) -> Any:
        subject.published_version_id = version.id
        if subject.published_at is None:
            subject.published_at = utc_now()
        return self.agent_repo.update(subject)

    def create_release(
        self,
        subject: Any,
        version: AgentVersion,
        *,
        scope: str,
        status: str,
        notes: str | None,
        previous_live_version_id: str | None,
        rollback_of_publish_id: str | None = None,
    ) -> Any:
        return self.publish_repo.create(
            AgentPublish(
                agent_id=subject.id,
                agent_version_id=version.id,
                scope=scope,
                status=status,
                notes=notes,
                rollback_of_publish_id=rollback_of_publish_id,
            )
        )

    def list_versions(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        return self.version_repo.list_by_agent(subject_id, limit=limit, offset=offset)

    def list_releases(self, subject_id: str, *, limit: int, offset: int) -> list[Any]:
        releases = self.publish_repo.list_by_agent(subject_id)
        return releases[offset : offset + limit]

    def find_release_id_for_version(self, subject_id: str, version_id: str | None) -> str | None:
        if not version_id:
            return None
        for release in self.publish_repo.list_by_agent(subject_id):
            if release.agent_version_id == version_id:
                return release.id
        return None

    def after_version_created(self, subject: Any, version: AgentVersion) -> None:
        self.sync_bindings(subject, version)
