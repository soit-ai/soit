"""Plugin packages are bounded before anything is unpacked."""

from __future__ import annotations

import io
import zipfile

import pytest

from app.kernel.commons.errors import ValidationError
from app.modules.plugin.infra.installer import PluginInstaller
from app.settings.settings import settings


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_an_archive_that_unpacks_past_the_limit_is_refused(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "plugins_dir", str(tmp_path))
    monkeypatch.setattr(settings, "plugin_package_max_extracted_bytes", 1024 * 1024)
    # Two megabytes of zeros compress to a few kilobytes: a small bomb.
    package = _zip({"plugin.json": b"{}", "padding.bin": b"\0" * (2 * 1024 * 1024)})
    assert len(package) < 64 * 1024

    with pytest.raises(ValidationError, match="unpacks to more than"):
        PluginInstaller().inspect_package(package)


def test_an_archive_with_too_many_entries_is_refused(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "plugins_dir", str(tmp_path))
    monkeypatch.setattr(settings, "plugin_package_max_entries", 3)
    package = _zip({f"file-{index}.txt": b"x" for index in range(4)})

    with pytest.raises(ValidationError, match="more than 3 entries"):
        PluginInstaller().inspect_package(package)


def test_an_oversized_package_is_refused_before_it_is_opened(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "plugins_dir", str(tmp_path))
    monkeypatch.setattr(settings, "plugin_package_max_bytes", 10)

    with pytest.raises(ValidationError, match="exceeds the 10 byte limit"):
        PluginInstaller().inspect_package(b"not a zip but too long anyway")
    with pytest.raises(ValidationError, match="exceeds the 10 byte limit"):
        PluginInstaller().install_from_bytes(
            tenant_id="t",
            workspace_id="w",
            plugin_name="p",
            version="1.0.0",
            package_bytes=b"not a zip but too long anyway",
        )
    assert not any(tmp_path.iterdir())
