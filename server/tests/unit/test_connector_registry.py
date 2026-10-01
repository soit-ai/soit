"""Connector registry: registration rules and the built-in kinds."""

from __future__ import annotations

import pytest

from app.kernel.ports.connectors import (
    ConnectorDescriptor,
    ConnectorError,
    ConnectorRegistration,
    ConnectorRegistry,
)
from app.wiring.connectors import build_connector_registry, get_connector_registry


def _registration(kind: str) -> ConnectorRegistration:
    return ConnectorRegistration(
        descriptor=ConnectorDescriptor(kind=kind, label=kind, description="", fields=()),
        validate_config=lambda config: dict(config),
        validate_credentials=lambda value: None,
        factory=lambda ctx, config, secret: None,  # type: ignore[arg-type, return-value]
    )


def test_registry_lists_kinds_in_a_stable_order() -> None:
    registry = ConnectorRegistry()
    registry.register(_registration("web"))
    registry.register(_registration("s3"))

    assert registry.kinds() == ["s3", "web"]
    assert [descriptor.kind for descriptor in registry.descriptors()] == ["s3", "web"]


def test_registering_a_kind_twice_is_refused() -> None:
    registry = ConnectorRegistry()
    registry.register(_registration("s3"))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_registration("s3"))


@pytest.mark.parametrize("kind", ["", "S3", "has space", "1abc", "x" * 40])
def test_malformed_kinds_are_refused(kind: str) -> None:
    with pytest.raises(ValueError, match="Invalid connector kind"):
        ConnectorRegistry().register(_registration(kind))


def test_unknown_kind_error_names_the_available_ones() -> None:
    registry = build_connector_registry()

    with pytest.raises(ConnectorError) as raised:
        registry.get("ftp")

    assert raised.value.code == ConnectorError.CONFIG_INVALID
    assert "s3" in raised.value.message


def test_built_in_registry_offers_s3() -> None:
    registry = build_connector_registry()

    assert "s3" in registry.kinds()
    descriptor = registry.get("s3").descriptor
    assert descriptor.secret == "required"


def test_shared_registry_is_built_once() -> None:
    assert get_connector_registry() is get_connector_registry()
