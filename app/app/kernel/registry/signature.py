""" signature

Integrity and signature verification utilities for plugin packages.

Current support
- SHA256 digest verification (always available)
- Optional public-key signature verification can be added later (ed25519/rsa).
"""

from __future__ import annotations

import hashlib
from typing import Optional


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
    """Placeholder for future signature verification.

    Returns False if cryptographic verification is not implemented.
    """
    # Intentionally not implemented (avoid forcing heavy crypto deps now).
    return False
