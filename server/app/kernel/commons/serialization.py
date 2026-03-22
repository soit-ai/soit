""" serialization

Stable serialization helpers for specs and trace.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    """Return a stable JSON string representation."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(payload: str) -> str:
    """Return SHA256 hex digest for a payload string."""
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def checksum_json(value: Any) -> str:
    """Return SHA256 checksum for a JSON-serializable value."""
    return sha256_hex(canonical_json(value))
