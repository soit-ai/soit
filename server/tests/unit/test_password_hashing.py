"""Passwords hash and verify with bcrypt, and the hashes passlib stored still verify."""

from __future__ import annotations

import pytest

from app.modules.identity.application.passwords import hash_password, verify_password

# Written by passlib 1.7.4 over bcrypt 4.0.1, as SOIT stored them before.
_SAMPLE = "correct horse battery staple"
_SAMPLE_STORED = "$2b$12$dP0Sox2/rElYh0cEgfdrmOVi6q12qfoz0dNgfoblFO4.ES.r9yWQm"
_LONG = "x" * 72 + "tail-past-seventy-two"
_LONG_STORED = "$2b$12$AS5QRKAHK04Jgbo0a9aXYOWhMHA5bGnj6zajBLtB2Se7ihmZQgoZy"
_ACCENTED = "pässwörd-ünïcode"
_ACCENTED_STORED = "$2b$12$R3cEzS0Wrg6bxYapyP5upOzymbcqSYqPHFX250j0eomEdh5lb7Y72"


@pytest.mark.parametrize(
    ("text", "stored"),
    [(_SAMPLE, _SAMPLE_STORED), (_LONG, _LONG_STORED), (_ACCENTED, _ACCENTED_STORED)],
)
def test_a_hash_passlib_stored_still_verifies(text: str, stored: str) -> None:
    assert verify_password(text, stored)
    assert not verify_password("wrong horse", stored)


def test_a_new_hash_verifies_and_is_bcrypt_at_the_same_cost() -> None:
    stored = hash_password(_SAMPLE)

    assert stored.startswith("$2b$12$")
    assert verify_password(_SAMPLE, stored)
    assert not verify_password("wrong horse", stored)


def test_a_password_past_72_bytes_is_cut_where_passlib_cut_it() -> None:
    stored = hash_password(_LONG)

    assert verify_password("x" * 72, stored)
    assert verify_password(_LONG, _LONG_STORED)


@pytest.mark.parametrize("stored", [None, "", "not-a-bcrypt-hash", "$2b$12$short"])
def test_no_hash_or_a_malformed_one_matches_nothing(stored: str | None) -> None:
    assert not verify_password(_SAMPLE, stored)
