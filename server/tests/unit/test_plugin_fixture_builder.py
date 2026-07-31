"""The generated plugin fixture must satisfy the installer it is built for.

A fixture that only looks signed would make the end-to-end suite prove nothing:
the install would pass because verification was skipped, not because the
signature was good.
"""

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.signature import payload_digest
from app.modules.plugin.infra.installer import PluginInstaller
from scripts.build_plugin_fixture import build_package, sign


def _installer(monkeypatch, **overrides) -> PluginInstaller:
    installer = PluginInstaller()
    for key, value in overrides.items():
        monkeypatch.setattr(installer.settings, key, value)
    return installer


def test_a_signed_fixture_passes_strict_verification(monkeypatch):
    package, manifest = build_package("fixture-plugin", "1.0.0")
    signed, public_key = sign(package, manifest)
    installer = _installer(
        monkeypatch,
        plugin_signature_required=True,
        plugin_integrity_required=True,
        plugin_signature_public_keys=[public_key],
    )

    _, spec = installer.inspect_package(signed)

    # inspect_package runs the same integrity checks the install path does.
    assert spec["name"] == "fixture-plugin"
    assert spec["integrity"]["digest"] == f"sha256:{payload_digest(signed)}"


def test_the_fixture_is_rejected_by_a_key_that_did_not_sign_it(monkeypatch):
    package, manifest = build_package("fixture-plugin", "1.0.0")
    signed, _ = sign(package, manifest)
    _, other_key = sign(*build_package("other", "1.0.0"))
    installer = _installer(
        monkeypatch,
        plugin_signature_required=True,
        plugin_signature_public_keys=[other_key],
    )

    with pytest.raises(ValidationError, match="verification failed"):
        installer.inspect_package(signed)


def test_an_unsigned_fixture_is_refused_under_strict_settings(monkeypatch):
    package, _ = build_package("fixture-plugin", "1.0.0")
    installer = _installer(
        monkeypatch,
        plugin_signature_required=True,
        plugin_signature_public_keys=["irrelevant"],
    )

    with pytest.raises(ValidationError, match="signature required"):
        installer.inspect_package(package)
