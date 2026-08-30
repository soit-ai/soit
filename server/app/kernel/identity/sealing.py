"""Seal small secrets at rest with a key derived from the application secret.

Used for values the application must be able to read back — a TOTP shared
secret has to be recomputed on every sign-in, so it cannot be hashed. Sealing
raises the bar from "a database dump is enough" to "a database dump plus the
application's secret key is enough", which is the same bar the session tokens
already sit behind.

This is not a substitute for a KMS. A deployment that needs key rotation or
hardware-held keys should put these values in Vault through the secrets port.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.kernel.commons.errors import KernelError


def _fernet(secret_key: str) -> Fernet:
    """Derive the sealing key from the application secret.

    SHA-256 of the configured secret, base64'd into Fernet's key format: the
    application secret is already required to be long and non-placeholder in
    production, so deriving from it inherits that requirement rather than
    introducing a second key nobody would rotate.
    """
    digest = hashlib.sha256((secret_key or "").encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(value: str, *, secret_key: str) -> str:
    """Return ``value`` sealed for storage."""
    return _fernet(secret_key).encrypt(value.encode("utf-8")).decode("ascii")


def unseal(sealed: str, *, secret_key: str) -> str:
    """Return the original value.

    Raises:
        KernelError: When the value cannot be opened — usually because the
            application secret changed, which orphans everything sealed under
            the old one. Failing loudly is the point: silently treating it as
            absent would quietly disable someone's second factor.
    """
    try:
        return _fernet(secret_key).decrypt(sealed.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise KernelError(
            "SEALED_VALUE_UNREADABLE",
            "A sealed value could not be opened with the current secret key",
        ) from exc
