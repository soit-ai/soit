"""Unit tests for the shared version control service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.contracts.context import RequestContext
from app.modules.versioning.application.service import (
    VersionControlService,
    VersioningAdapter,
)


class FakeAdapter(VersioningAdapter):
    subject_kind = "fake"

    def __init__(self) -> None:
        self.subject = SimpleNamespace(id="subject_1", current_version_id=None, published_version_id=None)
        self.versions: dict[str, SimpleNamespace] = {}
        self.releases: list[SimpleNamespace] = []
        self.counter = 0

    def get_subject(self, subject_id: str):
        return self.subject if subject_id == self.subject.id else None

    def get_version(self, version_id: str):
        return self.versions.get(version_id)

    def version_matches_subject(self, version, subject_id: str) -> bool:
        return version.subject_id == subject_id

    def next_version_number(self, subject_id: str) -> int:
        self.counter += 1
        return self.counter

    def create_version(self, subject_id: str, *, version_no: int, spec_schema: str, spec_json: dict, based_on_version_id: str | None, metadata: dict | None):
        version = SimpleNamespace(
            id=f"ver_{version_no}",
            subject_id=subject_id,
            version=version_no,
            spec_schema=spec_schema,
            spec_json=spec_json,
            status="draft",
            based_on_version_id=based_on_version_id,
        )
        self.versions[version.id] = version
        return version

    def update_version(self, version):
        self.versions[version.id] = version
        return version

    def update_head(self, subject, version):
        subject.current_version_id = version.id
        return subject

    def update_live(self, subject, version):
        subject.published_version_id = version.id
        return subject

    def create_release(self, subject, version, *, scope: str, status: str, notes: str | None, previous_live_version_id: str | None, rollback_of_publish_id: str | None = None):
        release = SimpleNamespace(
            version_id=version.id,
            status=status,
            previous_live_version_id=previous_live_version_id,
        )
        self.releases.append(release)
        return release

    def list_versions(self, subject_id: str, *, limit: int, offset: int):
        return list(self.versions.values())[offset : offset + limit]

    def list_releases(self, subject_id: str, *, limit: int, offset: int):
        return self.releases[offset : offset + limit]


class RequiredPublishApprovalGateway:
    def __init__(self, requires_approval: bool) -> None:
        self.requires_approval = requires_approval
        self.requests: list[dict] = []

    def evaluate(self, ctx: RequestContext, request: dict):
        self.requests.append(dict(request))
        return SimpleNamespace(
            requires_approval=self.requires_approval,
            reason="required_by_workspace_policy" if self.requires_approval else "no_matching_checkpoint_policy",
            policy_ref="approval:publish" if self.requires_approval else None,
            task_status="waiting_approval" if self.requires_approval else None,
            approval_payload={
                "title": request["title"],
                "details_json": request["details"],
            }
            if self.requires_approval
            else None,
        )


def _ctx() -> RequestContext:
    return RequestContext(
        tenant_id="tenant-1",
        workspace_id="workspace-1",
        user_id="user-1",
        request_id="req-1",
    )


def test_version_control_service_tracks_head_and_live_independently():
    adapter = FakeAdapter()
    service = VersionControlService(adapter)

    v1 = service.create_draft("subject_1", spec_schema="fake.v1", spec_json={"value": 1})
    v2 = service.create_draft("subject_1", spec_schema="fake.v1", spec_json={"value": 2})

    assert adapter.subject.current_version_id == v2.id
    assert adapter.subject.published_version_id is None
    assert v2.based_on_version_id == v1.id

    service.publish("subject_1", v2.id)
    assert adapter.subject.current_version_id == v2.id
    assert adapter.subject.published_version_id == v2.id
    assert adapter.releases[-1].status == "published"

    service.rollback("subject_1", v1.id)
    assert adapter.subject.current_version_id == v2.id
    assert adapter.subject.published_version_id == v1.id
    assert adapter.releases[-1].status == "rolled_back"
    assert adapter.releases[-1].previous_live_version_id == v2.id


def test_version_control_service_blocks_publish_when_approval_required():
    adapter = FakeAdapter()
    gateway = RequiredPublishApprovalGateway(requires_approval=True)
    service = VersionControlService(adapter, ctx=_ctx(), approval_checkpoint_gateway=gateway)
    version = service.create_draft("subject_1", spec_schema="fake.v1", spec_json={"value": 1})

    with pytest.raises(ValidationError) as exc:
        service.publish("subject_1", version.id, notes="release candidate")

    assert exc.value.details["status"] == "waiting_approval"
    assert exc.value.details["policy_ref"] == "approval:publish"
    assert adapter.subject.published_version_id is None
    assert adapter.releases == []
    assert version.status == "draft"
    assert gateway.requests == [
        {
            "action": "publish",
            "resource_type": "fake",
            "resource_ref": "fake:subject_1",
            "risk_level": "high",
            "run_id": None,
            "task_id": None,
            "thread_id": None,
            "agent_id": None,
            "title": "Approve publish: fake subject_1",
            "details": {
                "subject_kind": "fake",
                "subject_id": "subject_1",
                "version_id": version.id,
                "version": version.version,
                "scope": "workspace",
                "notes": "release candidate",
            },
        }
    ]


def test_version_control_service_publishes_when_approval_not_required():
    adapter = FakeAdapter()
    gateway = RequiredPublishApprovalGateway(requires_approval=False)
    service = VersionControlService(adapter, ctx=_ctx(), approval_checkpoint_gateway=gateway)
    version = service.create_draft("subject_1", spec_schema="fake.v1", spec_json={"value": 1})

    service.publish("subject_1", version.id)

    assert adapter.subject.published_version_id == version.id
    assert adapter.releases[-1].status == "published"
