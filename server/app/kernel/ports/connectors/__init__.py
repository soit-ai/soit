"""Knowledge connector port contracts."""

from app.kernel.ports.connectors.interface import (
    ConfigValidator,
    ConnectionReport,
    ConnectorDescriptor,
    ConnectorError,
    ConnectorFactory,
    ConnectorField,
    ConnectorItem,
    ConnectorOption,
    ConnectorRegistration,
    ConnectorRegistry,
    CredentialsValidator,
    FetchedItem,
    KnowledgeConnector,
    KnownItem,
)

__all__ = [
    "ConfigValidator",
    "ConnectionReport",
    "ConnectorDescriptor",
    "ConnectorError",
    "ConnectorFactory",
    "ConnectorField",
    "ConnectorItem",
    "ConnectorOption",
    "ConnectorRegistration",
    "ConnectorRegistry",
    "CredentialsValidator",
    "FetchedItem",
    "KnowledgeConnector",
    "KnownItem",
]
