""" signature

Integrity and signature verification utilities for plugin packages.

Current support
- SHA256 digest verification (always available)
- Optional public-key signature verification can be added later (ed25519/rsa).
"""

from __future__ import annotations

import base64
import hashlib


def sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def verify_sha256(data: bytes, expected_hex: str) -> bool:
    expected = (expected_hex or "").lower().strip()
    if not expected:
        return False
    return sha256_hex(data) == expected


def verify_signature(*, data: bytes, signature_b64: str, public_key_b64: str) -> bool:
    """Best-effort signature verification using optional crypto backend.

    Returns False if cryptographic verification is unavailable or fails.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except Exception:
        return False

    try:
        signature = base64.b64decode(signature_b64)
        public_key = base64.b64decode(public_key_b64)
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, data)
        return True
    except Exception:
        return False
