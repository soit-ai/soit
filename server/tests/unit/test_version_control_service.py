"""Unit tests for the shared version control service."""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.versioning.application.service import VersionControlService, VersioningAdapter


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
