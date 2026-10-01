"""SigV4 signing, pinned to AWS's published S3 examples."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from app.adapters.connectors import sigv4

# The access key, secret key, bucket and date used throughout AWS's documentation
# "Signature Calculations for the Authorization Header: Transferring Payload in
# a Single Chunk (AWS Signature Version 4)".
CREDENTIALS = sigv4.AwsCredentials("AKIAIOSFODNN7EXAMPLE", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
NOW = datetime(2013, 5, 24, 0, 0, 0, tzinfo=UTC)


def _signature(headers: dict[str, str]) -> str:
    return headers["Authorization"].rsplit("Signature=", 1)[1]


def test_get_object_with_range_matches_the_aws_example() -> None:
    headers = sigv4.sign_get(
        url="https://examplebucket.s3.amazonaws.com/test.txt",
        credentials=CREDENTIALS,
        region="us-east-1",
        now=NOW,
        extra_headers={"Range": "bytes=0-9"},
    )

    assert headers["Authorization"] == (
        "AWS4-HMAC-SHA256 Credential=AKIAIOSFODNN7EXAMPLE/20130524/us-east-1/s3/aws4_request,"
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date,"
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    assert headers["x-amz-date"] == "20130524T000000Z"
    assert headers["x-amz-content-sha256"] == sigv4.EMPTY_PAYLOAD_SHA256


def test_get_bucket_lifecycle_matches_the_aws_example() -> None:
    headers = sigv4.sign_get(
        url="https://examplebucket.s3.amazonaws.com/?lifecycle",
        credentials=CREDENTIALS,
        region="us-east-1",
        now=NOW,
    )

    assert _signature(headers) == "fea454ca298b7da1c68078a5d1bdbfbbe0d65c699e0f91ac7a200a0136783543"


def test_list_objects_with_query_matches_the_aws_example() -> None:
    headers = sigv4.sign_get(
        url="https://examplebucket.s3.amazonaws.com/?max-keys=2&prefix=J",
        credentials=CREDENTIALS,
        region="us-east-1",
        now=NOW,
    )

    assert _signature(headers) == "34b48302e7b5fa45bde8084f4b7868a86f0a534bc59db6670ed5711ef69dc6f7"


def test_query_parameter_order_does_not_change_the_signature() -> None:
    first = sigv4.sign_get(
        url="https://examplebucket.s3.amazonaws.com/?max-keys=2&prefix=J",
        credentials=CREDENTIALS,
        region="us-east-1",
        now=NOW,
    )
    second = sigv4.sign_get(
        url="https://examplebucket.s3.amazonaws.com/?prefix=J&max-keys=2",
        credentials=CREDENTIALS,
        region="us-east-1",
        now=NOW,
    )

    assert _signature(first) == _signature(second)


def test_session_token_is_signed_and_sent() -> None:
    credentials = sigv4.AwsCredentials("AKID", "secret", session_token="tok/en+1")
    headers = sigv4.sign_get(
        url="https://examplebucket.s3.amazonaws.com/a.txt",
        credentials=credentials,
        region="eu-west-1",
        now=NOW,
    )

    assert headers["x-amz-security-token"] == "tok/en+1"
    assert "x-amz-security-token" in headers["Authorization"]
    assert "eu-west-1/s3/aws4_request" in headers["Authorization"]


def test_host_with_a_port_is_part_of_the_signature() -> None:
    plain = sigv4.sign_get(url="https://minio.local/b/a.txt", credentials=CREDENTIALS, region="us-east-1", now=NOW)
    ported = sigv4.sign_get(url="https://minio.local:9000/b/a.txt", credentials=CREDENTIALS, region="us-east-1", now=NOW)

    assert _signature(plain) != _signature(ported)


def test_repr_never_shows_the_secret_key() -> None:
    assert "wJalrXUtnFEMI" not in repr(CREDENTIALS)
    assert "wJalrXUtnFEMI" not in str(CREDENTIALS)


@pytest.mark.parametrize(
    "key",
    [
        "plain/file.txt",
        "with space/and+plus (1).txt",
        "unicode/café über naïve.md",
        "symbols/a&b=c;d,e@f$g!h*'.txt",
        "tilde/~user/file.txt",
    ],
)
def test_signature_agrees_with_botocore_for_awkward_keys(key: str, monkeypatch) -> None:
    botocore_auth = pytest.importorskip("botocore.auth")
    awsrequest = pytest.importorskip("botocore.awsrequest")
    credentials_module = pytest.importorskip("botocore.credentials")

    class _FrozenDatetime(datetime):
        @classmethod
        def utcnow(cls):  # noqa: ANN206
            return NOW.replace(tzinfo=None)

        @classmethod
        def now(cls, tz=None):  # noqa: ANN206
            return NOW if tz else NOW.replace(tzinfo=None)

    monkeypatch.setattr(botocore_auth.datetime, "datetime", _FrozenDatetime)

    url = f"https://examplebucket.s3.amazonaws.com/{sigv4.encode_path(key)}"
    ours = sigv4.sign_get(url=url, credentials=CREDENTIALS, region="us-east-1", now=NOW)

    request = awsrequest.AWSRequest(method="GET", url=url, headers={})
    botocore_auth.S3SigV4Auth(
        credentials_module.Credentials(CREDENTIALS.access_key_id, CREDENTIALS.secret_access_key),
        "s3",
        "us-east-1",
    ).add_auth(request)

    assert _signature(ours) == request.headers["Authorization"].rsplit("Signature=", 1)[1]
    assert httpx.URL(url).raw_path.decode() == httpx.URL(str(httpx.URL(url))).raw_path.decode()
