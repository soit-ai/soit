"""Time-based one-time passwords (RFC 6238) and the codes that recover them.

Implemented against the RFC rather than pulled in as a dependency: the whole
construction is HMAC from the standard library plus the specified truncation,
and the RFC publishes test vectors, so the implementation can be checked
against the specification instead of trusted.

The secret itself is never stored in the clear — see the MFA service for how it
is sealed — and nothing here reads or writes state.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote

TIME_STEP_SECONDS = 30
"""The RFC's default step. Authenticator apps assume it; do not vary it."""

CODE_DIGITS = 6

DEFAULT_DRIFT_STEPS = 1
"""How many steps either side of now are accepted.

One step is 30 seconds of tolerance in each direction, which covers ordinary
clock drift on a phone. Widening this widens the window an intercepted code
stays usable in.
"""

RECOVERY_CODE_COUNT = 10
RECOVERY_CODE_BYTES = 5


def generate_secret(length: int = 20) -> str:
    """Return a fresh base32 secret of the RFC-recommended length.

    Twenty bytes matches the SHA-1 block the algorithm uses; shorter secrets
    weaken it, and longer ones buy nothing.
    """
    return base64.b32encode(secrets.token_bytes(length)).decode("ascii").rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    """One HOTP value (RFC 4226) for a counter."""
    padding = "=" * (-len(secret) % 8)
    key = base64.b32decode(secret.upper() + padding, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    # Dynamic truncation: the low nibble of the last byte picks the offset.
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**CODE_DIGITS)).zfill(CODE_DIGITS)


def generate_code(secret: str, timestamp: int) -> str:
    """Return the code valid at ``timestamp`` (epoch seconds)."""
    return _hotp(secret, timestamp // TIME_STEP_SECONDS)


def verify_code(
    secret: str,
    code: str,
    timestamp: int,
    *,
    drift_steps: int = DEFAULT_DRIFT_STEPS,
) -> bool:
    """Check a submitted code against the steps around ``timestamp``.

    Every candidate is compared in constant time, and every candidate is
    compared even after a match, so the number of comparisons does not reveal
    which step matched.
    """
    submitted = (code or "").strip().replace(" ", "")
    if not submitted.isdigit() or len(submitted) != CODE_DIGITS:
        return False

    counter = timestamp // TIME_STEP_SECONDS
    matched = False
    for step in range(-drift_steps, drift_steps + 1):
        candidate = _hotp(secret, counter + step)
        if hmac.compare_digest(candidate, submitted):
            matched = True
    return matched


def provisioning_uri(secret: str, *, account: str, issuer: str) -> str:
    """Build the otpauth:// URI an authenticator app scans."""
    label = quote(f"{issuer}:{account}", safe="")
    query = (
        f"secret={secret}"
        f"&issuer={quote(issuer, safe='')}"
        f"&algorithm=SHA1&digits={CODE_DIGITS}&period={TIME_STEP_SECONDS}"
    )
    return f"otpauth://totp/{label}?{query}"


def generate_recovery_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    """Return fresh single-use recovery codes.

    Formatted in two groups so they can be read aloud and typed back without
    ambiguity, and generated from the CSPRNG rather than from the TOTP secret:
    a recovery code has to survive the secret being lost.
    """
    codes = []
    for _ in range(count):
        raw = base64.b32encode(secrets.token_bytes(RECOVERY_CODE_BYTES)).decode("ascii")
        raw = raw.rstrip("=")
        codes.append(f"{raw[:4]}-{raw[4:8]}")
    return codes


def normalize_recovery_code(code: str) -> str:
    """Fold a typed recovery code to the form the stored hash was taken over."""
    return (code or "").strip().upper().replace(" ", "").replace("-", "")


def hash_recovery_code(code: str) -> str:
    """Hash a recovery code for storage.

    A plain SHA-256 rather than a password hash: these are 40 bits of CSPRNG
    output, not a human-chosen secret, so there is nothing for a slow hash to
    protect against that the entropy does not already cover.
    """
    return hashlib.sha256(normalize_recovery_code(code).encode("utf-8")).hexdigest()
