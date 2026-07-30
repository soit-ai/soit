"""Plugin package signature, digest and revocation enforcement."""

import base64

import pytest

from app.kernel.commons.errors import ValidationError
from app.kernel.registry.signature import sha256_hex
from app.modules.plugin.infra.installer import PluginInstaller

PACKAGE = b"plugin-package-bytes"
DIGEST = sha256_hex(PACKAGE)


def _installer(monkeypatch, **overrides) -> PluginInstaller:
    installer = PluginInstaller()
    for key, value in overrides.items():
        monkeypatch.setattr(installer.settings, key, value)
    return installer


def _spec(*, signature: str | None = None, digest: str | None = None) -> dict:
    integrity: dict[str, str] = {}
    if digest is not None:
        integrity["digest"] = digest
    if signature is not None:
        integrity["signature"] = signature
    return {"name": "demo", "version": "1.0.0", "integrity": integrity}


def test_unsigned_package_is_rejected_when_signatures_are_required(monkeypatch):
    installer = _installer(
        monkeypatch,
        plugin_signature_required=True,
        plugin_signature_public_keys=["key"],
    )

    with pytest.raises(ValidationError, match="signature required"):
        installer._check_integrity(spec=_spec(), digest=DIGEST)


def test_unverifiable_signature_is_rejected_when_signatures_are_required(monkeypatch):
    installer = _installer(
        monkeypatch,
        plugin_signature_required=True,
        plugin_signature_public_keys=[base64.b64encode(b"x" * 32).decode()],
    )

    with pytest.raises(ValidationError, match="verification failed"):
        installer._check_integrity(
            spec=_spec(signature=base64.b64encode(b"bogus").decode()),
            digest=DIGEST,
        )


def test_unsigned_package_is_allowed_when_signatures_are_optional(monkeypatch):
    installer = _installer(monkeypatch, plugin_signature_required=False)

    installer._check_integrity(spec=_spec(), digest=DIGEST)


def test_declared_digest_mismatch_is_rejected(monkeypatch):
    installer = _installer(
        monkeypatch,
        plugin_integrity_required=True,
        plugin_signature_required=False,
    )

    with pytest.raises(ValidationError, match="digest mismatch"):
        installer._check_integrity(
            spec=_spec(digest="sha256:" + "0" * 64),
            digest=DIGEST,
        )


def test_revoked_digest_is_rejected_even_without_signature_enforcement(monkeypatch):
    installer = _installer(
        monkeypatch,
        plugin_signature_required=False,
        plugin_revoked_package_digests=[f"sha256:{DIGEST}"],
    )

    # Revocation exists precisely for artifacts that pass verification, so it
    # must not depend on the signature settings.
    with pytest.raises(ValidationError, match="revoked"):
        installer._check_integrity(spec=_spec(), digest=DIGEST)


def test_revocation_accepts_a_bare_digest_and_ignores_case(monkeypatch):
    installer = _installer(
        monkeypatch,
        plugin_signature_required=False,
        plugin_revoked_package_digests=[DIGEST.upper()],
    )

    with pytest.raises(ValidationError, match="revoked"):
        installer._check_integrity(spec=_spec(), digest=DIGEST)


def test_unrevoked_digest_still_installs(monkeypatch):
    installer = _installer(
        monkeypatch,
        plugin_signature_required=False,
        plugin_revoked_package_digests=["sha256:" + "1" * 64],
    )

    installer._check_integrity(spec=_spec(), digest=DIGEST)
