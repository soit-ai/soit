"""Shared fakes for the knowledge connector tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.kernel.ports.connectors import (
    ConnectionReport,
    ConnectorDescriptor,
    ConnectorError,
    ConnectorField,
    ConnectorItem,
    ConnectorRegistration,
    ConnectorRegistry,
    FetchedItem,
    KnownItem,
)
from app.kernel.ports.secrets.interface import SecretsPort


@dataclass
class RemoteObject:
    content: bytes
    etag: str
    modified: str | None = None
    content_type: str = "text/plain"
    fail_fetch: str | None = None
    list_error: str | None = None


@dataclass
class FakeRemote:
    """A mutable stand-in for an external system."""

    objects: dict[str, RemoteObject] = field(default_factory=dict)
    list_failure: ConnectorError | None = None
    fail_after: int | None = None
    incomplete: bool = False
    fetches: list[str] = field(default_factory=list)
    seen_known: dict[str, KnownItem] = field(default_factory=dict)
    built_with: list[tuple[dict[str, Any], str | None]] = field(default_factory=list)

    def put(self, key: str, content: bytes, etag: str | None = None, **kwargs: Any) -> None:
        self.objects[key] = RemoteObject(content=content, etag=etag or f"etag-{key}-{len(content)}", **kwargs)


class FakeConnector:
    def __init__(self, remote: FakeRemote) -> None:
        self.remote = remote
        self._skipped = 0

    async def test_connection(self, *, sample_size: int = 10) -> ConnectionReport:
        return ConnectionReport(ok=True, message="ok")

    async def iter_items(self, known: Mapping[str, KnownItem]) -> AsyncIterator[ConnectorItem]:
        self.remote.seen_known = dict(known)
        if self.remote.list_failure is not None and self.remote.fail_after is None:
            raise self.remote.list_failure
        for index, (key, obj) in enumerate(sorted(self.remote.objects.items())):
            if self.remote.fail_after is not None and index >= self.remote.fail_after:
                raise self.remote.list_failure or ConnectorError(ConnectorError.LISTING_FAILED, "listing broke")
            yield ConnectorItem(
                external_id=key,
                name=key.rsplit("/", 1)[-1],
                source_uri=f"fake://bucket/{key}",
                etag=obj.etag,
                modified=obj.modified,
                size=len(obj.content),
                content_type=obj.content_type,
                error=obj.list_error,
            )

    async def fetch_item(self, item: ConnectorItem, *, max_bytes: int) -> FetchedItem:
        self.remote.fetches.append(item.external_id)
        obj = self.remote.objects[item.external_id]
        if obj.fail_fetch:
            raise ConnectorError(ConnectorError.ITEM_FAILED, obj.fail_fetch)
        return FetchedItem(content=obj.content, content_type=obj.content_type, filename=item.name, etag=obj.etag)

    def stats(self) -> Mapping[str, int]:
        return {"skipped": self._skipped, "incomplete": int(self.remote.incomplete)}


def build_registry(remote: FakeRemote, *, secret: str = "none") -> ConnectorRegistry:
    registry = ConnectorRegistry()

    def factory(ctx, config, secret_value):  # noqa: ARG001
        remote.built_with.append((dict(config), secret_value))
        return FakeConnector(remote)

    registry.register(
        ConnectorRegistration(
            descriptor=ConnectorDescriptor(
                kind="fake",
                label="Fake",
                description="A connector for tests",
                fields=(ConnectorField(key="bucket", label="Bucket", required=True),),
                secret=secret,  # type: ignore[arg-type]
            ),
            validate_config=lambda config: dict(config),
            validate_credentials=lambda value: None,
            factory=factory,
        )
    )
    return registry


class FakeSecretsPort(SecretsPort):
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self.values = values or {}
        self.requested: list[str] = []

    async def get_secret(self, secret_id: str, **kwargs: Any) -> str:
        self.requested.append(secret_id)
        if secret_id not in self.values:
            from app.kernel.commons.errors import NotFoundError

            raise NotFoundError("Secret not found")
        return self.values[secret_id]
