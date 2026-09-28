"""Signed Enterprise license files, read and verified by the Community runtime.

A license is a JSON envelope ``{"alg": "Ed25519", "payload": {...},
"signature": "<base64>"}`` whose signature covers the payload as canonical JSON
(sorted keys, no whitespace), the format the Enterprise issuer writes. The
payload names the license, the customer, when it was issued and when it
expires, and the feature keys it grants.

Without a license the runtime is Community, as it always was. A license that
verifies and has not expired makes it Enterprise with the license's feature
keys; one that has expired, fails its signature or cannot be read leaves it
Community and says why, so a lapsed or tampered license degrades the
deployment rather than stopping it.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, cast

LICENSE_ALGORITHM = "Ed25519"
CLOCK_SKEW = timedelta(minutes=5)
"""How far ahead of this host's clock a license may say it was issued."""


class LicenseStatus(str, Enum):
    ABSENT = "absent"
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALID = "invalid"


@dataclass(frozen=True)
class LicenseInfo:
    license_id: str
    customer_id: str
    issued_at: datetime
    expires_at: datetime
    entitlements: frozenset[str]


@dataclass(frozen=True)
class LicenseState:
    status: LicenseStatus
    license: LicenseInfo | None = None
    reason: str | None = None
    """Why a license present on disk grants nothing: expired, or what was wrong with it."""
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def edition(self) -> str:
        return "enterprise" if self.status is LicenseStatus.ACTIVE else "community"

    @property
    def entitlements(self) -> frozenset[str]:
        if self.status is LicenseStatus.ACTIVE and self.license is not None:
            return self.license.entitlements
        return frozenset()

    def days_left(self, now: datetime | None = None) -> int | None:
        if self.license is None:
            return None
        remaining = self.license.expires_at - (now or datetime.now(UTC))
        return max(0, remaining.days)


def canonical_payload(payload: dict[str, Any]) -> bytes:
    """The bytes a license signature covers."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _timestamp(value: Any, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"license {name} is not an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _payload(payload: dict[str, Any]) -> LicenseInfo:
    try:
        license_id = str(payload["license_id"]).strip()
        customer_id = str(payload["customer_id"]).strip()
        issued_at = _timestamp(payload["issued_at"], "issued_at")
        expires_at = _timestamp(payload["expires_at"], "expires_at")
    except KeyError as exc:
        raise ValueError(f"license payload has no {exc.args[0]}") from exc
    raw_entitlements: Any = payload.get("entitlements") or []
    if not isinstance(raw_entitlements, list):
        raise ValueError("license entitlements is not a list")
    if not license_id or not customer_id:
        raise ValueError("license_id and customer_id must not be empty")
    items: list[Any] = cast(list[Any], raw_entitlements)
    entitlements = frozenset(str(item).strip() for item in items if str(item).strip())
    return LicenseInfo(license_id, customer_id, issued_at, expires_at, entitlements)


def _public_key(pem_or_raw: bytes) -> Any:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    text = pem_or_raw.strip()
    if text.startswith(b"-----BEGIN"):
        key = load_pem_public_key(text)
        if not isinstance(key, Ed25519PublicKey):
            raise ValueError("the license public key is not an Ed25519 key")
        return key
    try:
        return Ed25519PublicKey.from_public_bytes(base64.b64decode(text, validate=True))
    except (binascii.Error, ValueError) as exc:
        raise ValueError("the license public key is neither PEM nor base64 Ed25519") from exc


def verify_license(envelope_json: str, public_key: bytes, *, now: datetime | None = None) -> LicenseState:
    """Verify a license envelope against ``public_key`` (PEM, or raw base64)."""
    from cryptography.exceptions import InvalidSignature

    current = (now or datetime.now(UTC)).astimezone(UTC)
    try:
        decoded: Any = json.loads(envelope_json)
        if not isinstance(decoded, dict):
            raise ValueError("the license file is not a JSON object")
        envelope = cast(dict[str, Any], decoded)
        if envelope.get("alg") != LICENSE_ALGORITHM:
            raise ValueError(f"the license is not signed with {LICENSE_ALGORITHM}")
        raw_payload: Any = envelope.get("payload")
        if not isinstance(raw_payload, dict):
            raise ValueError("the license has no payload object")
        payload = cast(dict[str, Any], raw_payload)
        signature = base64.b64decode(str(envelope.get("signature") or ""), validate=True)
        key = _public_key(public_key)
        try:
            key.verify(signature, canonical_payload(payload))
        except InvalidSignature as exc:
            raise ValueError("the license signature does not match its payload") from exc
        info = _payload(payload)
    except (ValueError, binascii.Error) as exc:
        return LicenseState(LicenseStatus.INVALID, reason=str(exc), checked_at=current)
    if info.issued_at > current + CLOCK_SKEW:
        return LicenseState(LicenseStatus.INVALID, info, "the license is not valid yet", current)
    if info.expires_at <= current:
        return LicenseState(LicenseStatus.EXPIRED, info, "the license has expired", current)
    return LicenseState(LicenseStatus.ACTIVE, info, checked_at=current)


def load_license(
    license_path: str | None,
    public_key_path: str | None,
    *,
    now: datetime | None = None,
) -> LicenseState:
    """Read the license and key files; no license path means Community."""
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if not license_path:
        return LicenseState(LicenseStatus.ABSENT, checked_at=current)
    if not public_key_path:
        return LicenseState(
            LicenseStatus.INVALID,
            reason="ENTERPRISE_LICENSE_PUBLIC_KEY_PATH is not set, so the license cannot be verified",
            checked_at=current,
        )
    try:
        envelope = Path(license_path).read_text(encoding="utf-8")
        key = Path(public_key_path).read_bytes()
    except OSError as exc:
        return LicenseState(
            LicenseStatus.INVALID,
            reason=f"cannot read {exc.filename}: {exc.strerror}",
            checked_at=current,
        )
    return verify_license(envelope, key, now=current)
