"""AWS Signature Version 4 request signing, for S3-compatible GET requests.

Written here, rather than taken from botocore, because the connector needs
signing and nothing else: botocore's client would make its own network calls
and bypass the governed egress path the connector must go through, and its
signer is an internal API of a package that is only a transitive dependency.
The surface needed is small and fully specified; the tests pin it to AWS's
published examples and cross-check it against botocore where that is installed.

Only requests without a body are supported, which is all listing and fetching
objects takes.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import httpx

ALGORITHM = "AWS4-HMAC-SHA256"
EMPTY_PAYLOAD_SHA256 = hashlib.sha256(b"").hexdigest()


@dataclass(frozen=True)
class AwsCredentials:
    """Static credentials, optionally with a session token."""

    access_key_id: str
    secret_access_key: str
    session_token: str | None = None

    def __repr__(self) -> str:
        return f"AwsCredentials(access_key_id={self.access_key_id!r}, secret_access_key='***')"


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()


def _encode_query_component(value: str) -> str:
    return quote(value, safe="-_.~")


def canonical_query(params: Mapping[str, str] | list[tuple[str, str]]) -> str:
    """The canonical query string: encoded, then sorted by name and value."""
    pairs = params.items() if isinstance(params, Mapping) else params
    encoded = sorted((_encode_query_component(name), _encode_query_component(value)) for name, value in pairs)
    return "&".join(f"{name}={value}" for name, value in encoded)


def encode_path(path: str) -> str:
    """Percent-encode an object path once, keeping the separators.

    S3 signs the path exactly as sent and does not encode it a second time, so
    the encoding applied here is what goes both on the wire and into the
    signature.
    """
    return quote(path, safe="/~")


def sign_get(
    *,
    url: str,
    credentials: AwsCredentials,
    region: str,
    now: datetime,
    service: str = "s3",
    extra_headers: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Headers that authorize a body-less GET of ``url``.

    ``url`` must already carry its final percent-encoded path and query; the
    request must be sent with exactly the returned headers added (the caller
    must not add or change any header that was signed). ``extra_headers`` are
    signed in addition to the host, content hash and date, such as ``range``.
    """
    parsed = httpx.URL(url)
    host = parsed.netloc.decode("ascii")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    headers: dict[str, str] = {
        "host": host,
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
    }
    if credentials.session_token:
        headers["x-amz-security-token"] = credentials.session_token
    for name, value in (extra_headers or {}).items():
        headers[name.lower()] = " ".join(value.split())

    signed_names = sorted(headers)
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in signed_names)
    signed_headers = ";".join(signed_names)

    query_pairs = [(name, value) for name, value in parsed.params.multi_items()]
    canonical_request = "\n".join(
        [
            "GET",
            parsed.raw_path.decode("ascii").split("?", 1)[0] or "/",
            canonical_query(query_pairs),
            canonical_headers,
            signed_headers,
            EMPTY_PAYLOAD_SHA256,
        ]
    )

    scope = f"{date_stamp}/{region}/{service}/aws4_request"
    string_to_sign = "\n".join(
        [
            ALGORITHM,
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    key = _hmac(("AWS4" + credentials.secret_access_key).encode("utf-8"), date_stamp)
    for part in (region, service, "aws4_request"):
        key = _hmac(key, part)
    signature = hmac.new(key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{ALGORITHM} Credential={credentials.access_key_id}/{scope},"
        f"SignedHeaders={signed_headers},Signature={signature}"
    )

    result = {
        "x-amz-content-sha256": EMPTY_PAYLOAD_SHA256,
        "x-amz-date": amz_date,
        "Authorization": authorization,
    }
    if credentials.session_token:
        result["x-amz-security-token"] = credentials.session_token
    for name, value in (extra_headers or {}).items():
        result[name] = value
    return result
