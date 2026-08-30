"""test_totp

Checked against the test vectors RFC 6238 publishes, so the implementation is
verified against the specification rather than against itself.
"""

import base64

from app.kernel.identity.totp import (
    CODE_DIGITS,
    generate_code,
    generate_recovery_codes,
    generate_secret,
    hash_recovery_code,
    normalize_recovery_code,
    provisioning_uri,
    verify_code,
)

# RFC 6238 Appendix B uses the ASCII seed "12345678901234567890" with SHA-1.
RFC_SECRET = base64.b32encode(b"12345678901234567890").decode("ascii")

RFC_VECTORS = [
    (59, "287082"),
    (1111111109, "081804"),
    (1111111111, "050471"),
    (1234567890, "005924"),
    (2000000000, "279037"),
    (20000000000, "353130"),
]


def test_codes_match_the_rfc_test_vectors():
    for timestamp, expected in RFC_VECTORS:
        assert generate_code(RFC_SECRET, timestamp) == expected


def test_a_code_verifies_within_its_own_step():
    timestamp = 1111111109
    code = generate_code(RFC_SECRET, timestamp)

    assert verify_code(RFC_SECRET, code, timestamp)


def test_clock_drift_of_one_step_is_tolerated_in_both_directions():
    """A phone thirty seconds out is common; a phone five minutes out is not."""
    timestamp = 1111111109
    code = generate_code(RFC_SECRET, timestamp)

    assert verify_code(RFC_SECRET, code, timestamp + 30)
    assert verify_code(RFC_SECRET, code, timestamp - 30)
    assert not verify_code(RFC_SECRET, code, timestamp + 300)


def test_a_malformed_code_is_refused_without_computing_anything():
    timestamp = 1111111109

    assert not verify_code(RFC_SECRET, "", timestamp)
    assert not verify_code(RFC_SECRET, "12345", timestamp)
    assert not verify_code(RFC_SECRET, "abcdef", timestamp)


def test_spaces_in_a_typed_code_are_tolerated():
    """Authenticator apps display codes in two groups; people type the space."""
    timestamp = 1111111109
    code = generate_code(RFC_SECRET, timestamp)
    spaced = f"{code[:3]} {code[3:]}"

    assert verify_code(RFC_SECRET, spaced, timestamp)


def test_a_generated_secret_is_usable_base32_of_the_recommended_length():
    secret = generate_secret()

    assert len(base64.b32decode(secret + "=" * (-len(secret) % 8))) == 20
    assert len(generate_code(secret, 1111111109)) == CODE_DIGITS


def test_the_provisioning_uri_names_the_issuer_and_account():
    uri = provisioning_uri("ABCDEFGH", account="ops@example.com", issuer="SOIT")

    assert uri.startswith("otpauth://totp/SOIT%3Aops%40example.com?")
    assert "secret=ABCDEFGH" in uri
    assert "issuer=SOIT" in uri
    assert "period=30" in uri


def test_recovery_codes_are_distinct_and_normalize_to_their_hash():
    codes = generate_recovery_codes()

    assert len(codes) == 10
    assert len(set(codes)) == 10
    # Typed back in any case, with or without the separator, hashes the same.
    for code in codes:
        assert hash_recovery_code(code) == hash_recovery_code(code.lower())
        assert hash_recovery_code(code) == hash_recovery_code(
            normalize_recovery_code(code)
        )


def test_two_secrets_do_not_produce_the_same_code():
    assert generate_code(generate_secret(), 59) != generate_code(generate_secret(), 59)
