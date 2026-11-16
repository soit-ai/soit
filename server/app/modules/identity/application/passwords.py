"""Password hashing with bcrypt.

The stored hashes are bcrypt's own ``$2b$`` strings, which passlib wrote
before SOIT called bcrypt directly, so they verify here unchanged. bcrypt
reads only the first 72 bytes of a password: passlib cut a longer one there
without a word, and bcrypt 5 refuses it instead, so it is cut here the same
way and a long password stored before still signs in.

A bcrypt hash or check costs a few hundred milliseconds of CPU on purpose.
Request handlers use the ``*_async`` forms, which run it on a worker thread:
on the event loop, every sign-in would stall the whole process for that long.
"""

from __future__ import annotations

import anyio
import bcrypt

_BCRYPT_MAX_BYTES = 72


def _bytes(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """A new bcrypt hash of ``password``, at bcrypt's default cost."""
    return bcrypt.hashpw(_bytes(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str | None) -> bool:
    """Whether ``password`` matches ``password_hash``; no hash, or a malformed one, matches nothing."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_bytes(password), password_hash.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return False


async def hash_password_async(password: str) -> str:
    """:func:`hash_password` on a worker thread."""
    return await anyio.to_thread.run_sync(hash_password, password)


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    """:func:`verify_password` on a worker thread."""
    return await anyio.to_thread.run_sync(verify_password, password, password_hash)
