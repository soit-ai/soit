"""Knowledge connector contract.

A connector reads documents out of one kind of external system (an object
store, a website) so a knowledge base can be kept in step with it. The contract
is deliberately small: describe the remote, list what is there, fetch one item.
Everything that decides *what to do* with the answer -- change detection,
versioning, removals, scheduling, caps -- lives in the knowledge sync service,
so a connector holds no state between runs and cannot bypass those rules.

Implementations reach the network only through the governed egress path and
receive credentials already resolved from a secret by the caller; they never
see or store a secret id.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable

from app.kernel.commons.errors import KernelError
from app.kernel.contracts.context import RequestContext

FieldType = Literal["string", "text", "integer", "boolean", "string_list", "select"]


class ConnectorError(KernelError):
    """A connector could not do what it was asked.

    ``code`` separates the causes an operator acts on differently: a bad
    configuration, rejected credentials, an unreachable or egress-refused
    endpoint, and a problem with one item.
    """

    CONFIG_INVALID = "CONNECTOR_CONFIG_INVALID"
    CREDENTIALS_INVALID = "CONNECTOR_CREDENTIALS_INVALID"
    AUTH_FAILED = "CONNECTOR_AUTH_FAILED"
    UNREACHABLE = "CONNECTOR_UNREACHABLE"
    EGRESS_BLOCKED = "CONNECTOR_EGRESS_BLOCKED"
    LISTING_FAILED = "CONNECTOR_LISTING_FAILED"
    ITEM_FAILED = "CONNECTOR_ITEM_FAILED"
    ITEM_TOO_LARGE = "CONNECTOR_ITEM_TOO_LARGE"

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(code, message, details)


@dataclass(frozen=True)
class ConnectorOption:
    """One choice of a ``select`` field."""

    value: str
    label: str


@dataclass(frozen=True)
class ConnectorField:
    """One configuration field a connector accepts, as a form would render it."""

    key: str
    label: str
    type: FieldType = "string"
    required: bool = False
    default: Any = None
    help: str | None = None
    placeholder: str | None = None
    options: tuple[ConnectorOption, ...] = ()
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True)
class ConnectorDescriptor:
    """What a connector kind is and which configuration it takes."""

    kind: str
    label: str
    description: str
    fields: tuple[ConnectorField, ...]
    secret: Literal["none", "optional", "required"] = "none"
    secret_help: str | None = None
    """What the secret's value must look like, shown beside the secret picker."""


@dataclass(frozen=True)
class ConnectorItem:
    """One remote document, as listed.

    ``external_id`` is the remote's stable identity for the item (an object
    key, a normalized URL); everything else is a hint used to tell whether it
    changed since the last sync.
    """

    external_id: str
    name: str
    source_uri: str | None = None
    etag: str | None = None
    modified: str | None = None
    """Remote modification marker, compared as an opaque string."""

    size: int | None = None
    content_type: str | None = None
    meta: dict[str, Any] = field(default_factory=dict[str, Any])
    """Connector-private state kept per item and handed back next run."""

    error: str | None = None
    """Set when the item is known to exist but could not be read this run.

    The item is reported failed and, importantly, never treated as removed.
    """


@dataclass(frozen=True)
class KnownItem:
    """What the previous sync recorded about an item, offered to the connector."""

    etag: str | None
    modified: str | None
    meta: dict[str, Any]


@dataclass(frozen=True)
class FetchedItem:
    """The content of one item."""

    content: bytes
    content_type: str
    filename: str | None = None
    title: str | None = None
    etag: str | None = None
    modified: str | None = None


@dataclass(frozen=True)
class ConnectionReport:
    """Outcome of a connection test."""

    ok: bool
    message: str
    sample: tuple[ConnectorItem, ...] = ()


@runtime_checkable
class KnowledgeConnector(Protocol):
    """One configured connection to an external system."""

    async def test_connection(self, *, sample_size: int = 10) -> ConnectionReport:
        """Check the endpoint and credentials, and list a few items.

        Nothing is ingested. A failure is reported rather than raised where the
        cause is something the operator can act on.
        """
        ...

    def iter_items(self, known: Mapping[str, KnownItem]) -> AsyncIterator[ConnectorItem]:
        """Yield every item currently in the remote.

        An item missing from the iteration is taken to be gone, so a connector
        must raise ``ConnectorError`` rather than end the iteration early when
        the listing fails part way. ``known`` lets a connector avoid work for
        items that have not changed.
        """
        ...

    async def fetch_item(self, item: ConnectorItem, *, max_bytes: int) -> FetchedItem:
        """Download one item, refusing anything larger than ``max_bytes``."""
        ...

    def stats(self) -> Mapping[str, int]:
        """Counters from the current run, such as items skipped as unsupported."""
        ...


ConnectorFactory = Callable[
    [RequestContext, Mapping[str, Any], str | None],
    KnowledgeConnector,
]
"""``factory(ctx, config, secret_value)``: build a connector for one source."""

ConfigValidator = Callable[[Mapping[str, Any]], dict[str, Any]]
"""Validate a source's config, returning it normalized, or raise ConnectorError."""

CredentialsValidator = Callable[[str | None], None]
"""Check the shape of a resolved secret value without ever echoing it."""

_KIND_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


@dataclass(frozen=True)
class ConnectorRegistration:
    """A connector kind together with how to validate and build it."""

    descriptor: ConnectorDescriptor
    validate_config: ConfigValidator
    validate_credentials: CredentialsValidator
    factory: ConnectorFactory


class ConnectorRegistry:
    """The connector kinds a deployment offers."""

    def __init__(self) -> None:
        self._registrations: dict[str, ConnectorRegistration] = {}

    def register(self, registration: ConnectorRegistration) -> None:
        """Add a connector kind; registering a kind twice is a programming error."""
        kind = registration.descriptor.kind
        if not _KIND_PATTERN.match(kind):
            raise ValueError(f"Invalid connector kind: {kind!r}")
        if kind in self._registrations:
            raise ValueError(f"Connector kind already registered: {kind}")
        self._registrations[kind] = registration

    def get(self, kind: str) -> ConnectorRegistration:
        """The registration for ``kind``, or a configuration error naming the kinds there are."""
        registration = self._registrations.get(kind)
        if registration is None:
            known = ", ".join(sorted(self._registrations)) or "none"
            raise ConnectorError(
                ConnectorError.CONFIG_INVALID,
                f"Unknown connector kind {kind!r}; available kinds: {known}",
            )
        return registration

    def descriptors(self) -> list[ConnectorDescriptor]:
        """Every registered kind's descriptor, in a stable order."""
        return [self._registrations[kind].descriptor for kind in sorted(self._registrations)]

    def kinds(self) -> list[str]:
        return sorted(self._registrations)
