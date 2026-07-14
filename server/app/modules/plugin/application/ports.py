"""Application-layer ports for the plugin module."""

from __future__ import annotations

from typing import Protocol, Optional, Sequence, Any

from app.modules.plugin.domain.models import Plugin, PluginInstallation


class PluginRepositoryPort(Protocol):
    def get(self, plugin_id: str) -> Optional[Plugin]: ...
    def get_by_name_version(self, name: str, version: str) -> Optional[Plugin]: ...
    def create(self, plugin: Plugin) -> Plugin: ...
    def update(self, plugin: Plugin) -> Plugin: ...
    def delete(self, plugin: Plugin) -> None: ...
    def list(
        self,
        published_only: bool = False,
        plugin_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Sequence[Plugin]: ...


class PluginInstallationRepositoryPort(Protocol):
    def get(self, installation_id: str) -> Optional[PluginInstallation]: ...
    def get_by_plugin(self, plugin_id: str) -> Optional[PluginInstallation]: ...
    def create(self, installation: PluginInstallation) -> PluginInstallation: ...
    def delete(self, installation: PluginInstallation) -> None: ...
    def list_by_workspace(self, limit: int = 100, offset: int = 0) -> Sequence[PluginInstallation]: ...
    def list_by_plugin(self, plugin_id: str) -> Sequence[PluginInstallation]: ...


class PluginInstallerPort(Protocol):
    """Port for plugin installation/extraction.

    Application code depends on this protocol so we can swap installation
    strategies (filesystem, object storage, remote runtime) without changing
    application logic.
    """

    def install_from_bytes(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        plugin_name: str,
        version: str,
        package_bytes: bytes,
        expected_sha256: str | None = None,
    ) -> list[str]:
        """Install plugin package bytes and return installed file paths."""
        ...
