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


def test_production_settings_can_actually_install_a_package(monkeypatch):
    """The strict profile must be satisfiable, not merely strict.

    The declared digest lives inside the archive. Comparing it to the archive's
    own hash is self-referential — writing the value changes the thing being
    hashed — so requiring integrity would have made every install impossible.
    Hashing the payload without the manifest is what makes the requirement
    something a publisher can meet.
    """
    from scripts.build_plugin_fixture import build_package, sign

    package, manifest = build_package("strict-profile-plugin", "1.0.0")
    signed, public_key = sign(package, manifest)
    installer = _installer(
        monkeypatch,
        plugin_signature_required=True,
        plugin_integrity_required=True,
        plugin_signature_public_keys=[public_key],
    )

    _, spec = installer.inspect_package(signed)

    assert spec["name"] == "strict-profile-plugin"


def test_a_package_declaring_no_digest_is_refused_when_integrity_is_required(monkeypatch):
    installer = _installer(
        monkeypatch,
        plugin_integrity_required=True,
        plugin_signature_required=False,
    )

    # Skipping the check because nothing was declared would let any package
    # opt out of the requirement simply by staying silent.
    with pytest.raises(ValidationError, match="must declare an integrity digest"):
        installer._check_integrity(spec=_spec(), digest=DIGEST)
