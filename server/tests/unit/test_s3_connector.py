"""S3 connector: listing, fetching, signing, config and egress."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import parse_qs

import httpx
import pytest

from app.adapters.connectors import s3, sigv4
from app.adapters.connectors.common import RESOURCE_S3, make_client
from app.kernel.ports.connectors import ConnectorError, ConnectorItem
from app.kernel.security import egress
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)
CREDENTIALS = sigv4.AwsCredentials("AKIDEXAMPLE", "very-secret-key-value")
SECRET_JSON = json.dumps({"access_key_id": "AKIDEXAMPLE", "secret_access_key": "very-secret-key-value"})

NS = "http://s3.amazonaws.com/doc/2006-03-01/"


class PublicResolver:
    def __init__(self, address: str = "93.184.216.34") -> None:
        self.address = address
        self.hosts: list[str] = []

    async def resolve(self, hostname: str, port: int) -> list[str]:
        self.hosts.append(hostname)
        return [self.address]


@pytest.fixture(autouse=True)
def egress_policy(monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["*.amazonaws.com", "minio.example.com", "s3.amazonaws.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(settings, "egress_private_networks", [])
    monkeypatch.setattr(egress, "_egress_policy", None)


def contents(key: str, *, etag: str = "abc", size: int = 5, modified: str = "2026-09-30T10:00:00.000Z") -> str:
    return (
        f"<Contents><Key>{key}</Key><LastModified>{modified}</LastModified>"
        f'<ETag>&quot;{etag}&quot;</ETag><Size>{size}</Size><StorageClass>STANDARD</StorageClass></Contents>'
    )


def listing(*entries: str, token: str | None = None) -> bytes:
    truncated = f"<IsTruncated>true</IsTruncated><NextContinuationToken>{token}</NextContinuationToken>" if token else (
        "<IsTruncated>false</IsTruncated>"
    )
    return f'<?xml version="1.0"?><ListBucketResult xmlns="{NS}"><Name>docs</Name>{truncated}{"".join(entries)}</ListBucketResult>'.encode()


class FakeS3:
    """Answers like S3, and checks every request is signed for the URL it was sent to."""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.pages: list[bytes] = []
        self.objects: dict[str, bytes] = {}
        self.fail: tuple[int, str, dict[str, str]] | None = None

    def check_signature(self, request: httpx.Request) -> bool:
        stamp = request.headers["x-amz-date"]
        moment = datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        expected = sigv4.sign_get(url=str(request.url), credentials=CREDENTIALS, region="us-east-1", now=moment)
        return request.headers["Authorization"] == expected["Authorization"]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.check_signature(request):
            return httpx.Response(403, content=b"<Error><Code>SignatureDoesNotMatch</Code><Message>bad</Message></Error>")
        if self.fail:
            status, code, headers = self.fail
            return httpx.Response(status, headers=headers, content=f"<Error><Code>{code}</Code><Message>nope</Message></Error>".encode())
        query = parse_qs(request.url.query.decode())
        if query.get("list-type") == ["2"]:
            index = len([r for r in self.requests if b"list-type" in r.url.query]) - 1
            return httpx.Response(200, content=self.pages[index])
        key = request.url.path.split("/", 2)[-1] if request.url.host.startswith("minio") else request.url.path.lstrip("/")
        from urllib.parse import unquote

        key = unquote(key)
        if key not in self.objects:
            return httpx.Response(404, content=b"<Error><Code>NoSuchKey</Code><Message>missing</Message></Error>")
        return httpx.Response(200, content=self.objects[key])


def build(ctx, fake: FakeS3, config: dict | None = None, *, resolver=None) -> s3.S3Connector:
    guard = GovernedEgressGuard(address_resolver=resolver or PublicResolver())
    normalized = s3.validate_config({"bucket": "docs", **(config or {})})

    def factory() -> httpx.AsyncClient:
        return make_client(ctx, RESOURCE_S3, egress_guard=guard, transport=httpx.MockTransport(fake))

    return s3.S3Connector(ctx, normalized, CREDENTIALS, client_factory=factory, clock=lambda: NOW)


async def collect(connector: s3.S3Connector) -> list[ConnectorItem]:
    return [item async for item in connector.iter_items({})]


# ---------------------------------------------------------------- listing


@pytest.mark.asyncio
async def test_listing_follows_continuation_tokens_and_describes_items(ctx) -> None:
    fake = FakeS3()
    token = "1ueGcxLPRx1Tr/XYExHnhbYLgveDs2J/wm36Hy4vbOwM="
    fake.pages = [
        listing(contents("handbook/a.pdf", etag="e1", size=10), contents("handbook/b.md", etag="e2", size=20), token=token),
        listing(contents("handbook/c.txt", etag="e3", size=30)),
    ]
    connector = build(ctx, fake, {"prefix": "/handbook/"})

    items = await collect(connector)

    assert [item.external_id for item in items] == ["handbook/a.pdf", "handbook/b.md", "handbook/c.txt"]
    first = items[0]
    assert first.name == "a.pdf" and first.etag == "e1" and first.size == 10
    assert first.source_uri == "s3://docs/handbook/a.pdf"
    assert first.content_type == "application/pdf" and first.modified == "2026-09-30T10:00:00.000Z"
    assert items[1].content_type == "text/markdown"
    assert len(fake.requests) == 2
    second_query = parse_qs(fake.requests[1].url.query.decode())
    assert second_query["continuation-token"] == [token]
    assert second_query["prefix"] == ["handbook/"]
    assert fake.requests[0].url.host == "docs.s3.amazonaws.com"


@pytest.mark.asyncio
async def test_listing_skips_folders_unsupported_types_and_filtered_keys(ctx) -> None:
    fake = FakeS3()
    fake.pages = [
        listing(
            contents("docs/"),
            contents("docs/keep.txt"),
            contents("docs/image.png"),
            contents("docs/drafts/skip.txt"),
            contents("other/outside.txt"),
            contents("docs/readme.md"),
        )
    ]
    connector = build(ctx, fake, {"include": ["docs/*"], "exclude": ["docs/drafts/*"]})

    items = await collect(connector)

    assert [item.external_id for item in items] == ["docs/keep.txt", "docs/readme.md"]
    assert connector.stats()["skipped"] == 4


@pytest.mark.asyncio
async def test_listing_signs_requests_for_awkward_keys(ctx) -> None:
    fake = FakeS3()
    key = "reports/Q3 results (final)+v2 é.txt"
    fake.objects[key] = b"numbers"
    connector = build(ctx, fake)

    fetched = await connector.fetch_item(
        ConnectorItem(external_id=key, name="x", etag="e", size=7, content_type="text/plain"), max_bytes=1000
    )

    assert fetched.content == b"numbers"
    assert fetched.content_type == "text/plain" and fetched.filename == "Q3 results (final)+v2 é.txt"
    assert fake.requests[0].headers["Authorization"].startswith("AWS4-HMAC-SHA256 Credential=AKIDEXAMPLE/20261001/")


@pytest.mark.asyncio
async def test_fetch_item_refuses_an_object_over_the_byte_limit(ctx) -> None:
    fake = FakeS3()
    fake.objects["big.txt"] = b"x" * 100
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError) as raised:
        await connector.fetch_item(ConnectorItem(external_id="big.txt", name="big.txt"), max_bytes=10)

    assert raised.value.code == ConnectorError.ITEM_TOO_LARGE


@pytest.mark.asyncio
async def test_fetch_of_a_vanished_object_is_an_item_failure(ctx) -> None:
    connector = build(ctx, FakeS3())

    with pytest.raises(ConnectorError) as raised:
        await connector.fetch_item(ConnectorItem(external_id="gone.txt", name="gone.txt"), max_bytes=10)

    assert raised.value.code == ConnectorError.ITEM_FAILED
    assert "no longer exists" in raised.value.message


@pytest.mark.asyncio
async def test_rejected_credentials_fail_the_listing_with_the_service_error_code(ctx) -> None:
    fake = FakeS3()
    fake.fail = (403, "InvalidAccessKeyId", {})
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError) as raised:
        await collect(connector)

    assert raised.value.code == ConnectorError.AUTH_FAILED
    assert "InvalidAccessKeyId" in raised.value.message
    assert "very-secret-key-value" not in raised.value.message


@pytest.mark.asyncio
async def test_wrong_region_is_reported_with_the_right_one(ctx) -> None:
    fake = FakeS3()
    fake.fail = (301, "PermanentRedirect", {"x-amz-bucket-region": "eu-west-1"})
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError) as raised:
        await collect(connector)

    assert "eu-west-1" in raised.value.message


@pytest.mark.asyncio
async def test_missing_bucket_is_a_listing_failure(ctx) -> None:
    fake = FakeS3()
    fake.fail = (404, "NoSuchBucket", {})
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError) as raised:
        await collect(connector)

    assert raised.value.code == ConnectorError.LISTING_FAILED and "bucket was not found" in raised.value.message


@pytest.mark.asyncio
async def test_a_response_that_is_not_s3_is_explained(ctx) -> None:
    fake = FakeS3()
    fake.pages = [b"<html><body>Welcome to nginx</body></html>"]
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError) as raised:
        await collect(connector)

    assert "did not answer like an S3 service" in raised.value.message


@pytest.mark.asyncio
async def test_xml_with_entity_declarations_is_refused(ctx) -> None:
    fake = FakeS3()
    fake.pages = [b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><ListBucketResult>&a;</ListBucketResult>']
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError):
        await collect(connector)


@pytest.mark.asyncio
async def test_truncated_listing_without_a_token_is_an_error_not_a_short_listing(ctx) -> None:
    fake = FakeS3()
    fake.pages = [
        f'<ListBucketResult xmlns="{NS}"><IsTruncated>true</IsTruncated>{contents("a.txt")}</ListBucketResult>'.encode()
    ]
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError):
        await collect(connector)


@pytest.mark.asyncio
async def test_unreachable_endpoint_is_reported_without_a_stack_of_internals(ctx) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    guard = GovernedEgressGuard(address_resolver=PublicResolver())
    connector = s3.S3Connector(
        ctx,
        s3.validate_config({"bucket": "docs"}),
        CREDENTIALS,
        client_factory=lambda: make_client(ctx, RESOURCE_S3, egress_guard=guard, transport=httpx.MockTransport(refuse)),
        clock=lambda: NOW,
    )

    with pytest.raises(ConnectorError) as raised:
        await collect(connector)

    assert raised.value.code == ConnectorError.UNREACHABLE
    assert "docs.s3.amazonaws.com" in raised.value.message


# ------------------------------------------------------------------ egress


@pytest.mark.asyncio
async def test_private_address_is_refused_by_the_governed_egress(ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "egress_allowlist", ["minio.internal"])
    monkeypatch.setattr(egress, "_egress_policy", None)
    fake = FakeS3()
    connector = build(
        ctx,
        fake,
        {"endpoint": "https://minio.internal:9000"},
        resolver=PublicResolver("10.1.2.3"),
    )

    with pytest.raises(ConnectorError) as raised:
        await collect(connector)

    assert raised.value.code == ConnectorError.EGRESS_BLOCKED
    assert "minio.internal" in raised.value.message
    assert "EGRESS_PRIVATE_NETWORKS" in raised.value.message
    assert fake.requests == []

    report = await connector.test_connection()
    assert report.ok is False and "egress policy" in report.message
    assert fake.requests == []


@pytest.mark.asyncio
async def test_private_endpoint_works_once_its_network_is_opened(ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "egress_allowlist", ["minio.internal"])
    monkeypatch.setattr(settings, "egress_private_networks", ["10.0.0.0/8"])
    monkeypatch.setattr(egress, "_egress_policy", None)
    fake = FakeS3()
    fake.pages = [listing(contents("a.txt"))]
    connector = build(ctx, fake, {"endpoint": "https://minio.internal:9000"}, resolver=PublicResolver("10.1.2.3"))

    items = await collect(connector)

    assert [item.external_id for item in items] == ["a.txt"]
    assert fake.requests[0].url.host == "minio.internal" and fake.requests[0].url.port == 9000
    assert fake.requests[0].url.path == "/docs/"


@pytest.mark.asyncio
async def test_host_outside_the_allowlist_is_refused(ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "egress_allowlist", ["something-else.example.com"])
    monkeypatch.setattr(egress, "_egress_policy", None)
    fake = FakeS3()
    connector = build(ctx, fake)

    with pytest.raises(ConnectorError) as raised:
        await collect(connector)

    assert raised.value.code == ConnectorError.EGRESS_BLOCKED
    assert fake.requests == []


# ------------------------------------------------------------ test connection


@pytest.mark.asyncio
async def test_test_connection_samples_matching_objects_without_fetching(ctx) -> None:
    fake = FakeS3()
    fake.pages = [listing(*(contents(f"d/{n}.txt") for n in range(30)))]
    connector = build(ctx, fake)

    report = await connector.test_connection(sample_size=5)

    assert report.ok is True
    assert len(report.sample) == 5
    assert "5 matching objects" in report.message
    assert len(fake.requests) == 1


@pytest.mark.asyncio
async def test_test_connection_reports_auth_failures_instead_of_raising(ctx) -> None:
    fake = FakeS3()
    fake.fail = (403, "AccessDenied", {})
    connector = build(ctx, fake)

    report = await connector.test_connection()

    assert report.ok is False and "AccessDenied" in report.message


@pytest.mark.asyncio
async def test_test_connection_says_when_nothing_matches(ctx) -> None:
    fake = FakeS3()
    fake.pages = [listing(contents("photo.png"))]
    connector = build(ctx, fake)

    report = await connector.test_connection()

    assert report.ok is True and report.sample == ()
    assert "no matching objects" in report.message


# ----------------------------------------------------------------- addressing


@pytest.mark.parametrize(
    ("config", "expected"),
    [
        ({"bucket": "docs"}, "https://docs.s3.amazonaws.com/?list-type=2"),
        ({"bucket": "docs", "region": "eu-west-1"}, "https://docs.s3.eu-west-1.amazonaws.com/?list-type=2"),
        ({"bucket": "my.docs"}, "https://s3.amazonaws.com/my.docs/?list-type=2"),
        ({"bucket": "docs", "endpoint": "https://minio.example.com:9000"}, "https://minio.example.com:9000/docs/?list-type=2"),
        (
            {"bucket": "docs", "endpoint": "https://r2.example.com", "path_style": False},
            "https://docs.r2.example.com/?list-type=2",
        ),
    ],
)
def test_addressing_styles(ctx, config, expected) -> None:
    connector = s3.S3Connector(ctx, s3.validate_config(config), CREDENTIALS)

    assert connector._url(None, [("list-type", "2")]) == expected


# ------------------------------------------------------------ config + secret


def test_config_is_normalized_with_defaults() -> None:
    config = s3.validate_config({"bucket": "docs", "prefix": "/a/b/", "include": [" *.pdf ", ""]})

    assert config == {
        "bucket": "docs",
        "region": "us-east-1",
        "endpoint": None,
        "prefix": "a/b/",
        "include": ["*.pdf"],
        "exclude": [],
        "path_style": False,
    }
    assert s3.validate_config({"bucket": "docs", "endpoint": "http://localhost:9000/"})["endpoint"] == "http://localhost:9000"
    assert s3.validate_config({"bucket": "docs", "endpoint": "http://localhost:9000"})["path_style"] is True


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({}, "bucket is required"),
        ({"bucket": "ab"}, "not a valid bucket"),
        ({"bucket": "docs", "endpoint": "ftp://x"}, "http or https"),
        ({"bucket": "docs", "endpoint": "https://user:pw@x.example.com"}, "credentials"),
        ({"bucket": "docs", "endpoint": "https://x.example.com/path"}, "path"),
        ({"bucket": "docs", "region": "us east"}, "region"),
        ({"bucket": "docs", "include": "*.pdf"}, "list"),
        ({"bucket": "docs", "path_style": "yes"}, "true or false"),
        ({"bucket": "docs", "mystery": 1}, "Unknown setting: mystery"),
    ],
)
def test_invalid_config_is_rejected_with_a_reason(config, message) -> None:
    with pytest.raises(ConnectorError) as raised:
        s3.validate_config(config)

    assert raised.value.code == ConnectorError.CONFIG_INVALID
    assert message in raised.value.message


@pytest.mark.parametrize("key", ["access_key_id", "secret_access_key", "session_token", "password", "api_key"])
def test_credentials_in_the_config_are_refused_and_never_echoed(key) -> None:
    with pytest.raises(ConnectorError) as raised:
        s3.validate_config({"bucket": "docs", key: "hunter2-value"})

    assert "looks like a credential" in raised.value.message
    assert "hunter2-value" not in raised.value.message


def test_credentials_are_parsed_from_the_secret_json() -> None:
    parsed = s3.parse_credentials(
        json.dumps({"access_key_id": "AK", "secret_access_key": "SK", "session_token": "TOK"})
    )

    assert (parsed.access_key_id, parsed.secret_access_key, parsed.session_token) == ("AK", "SK", "TOK")


@pytest.mark.parametrize(
    "value",
    [None, "", "not json hunter2", "[1, 2]", json.dumps({"access_key_id": "AK"}), json.dumps({"secret_access_key": "SK"})],
)
def test_bad_secret_values_are_rejected_without_repeating_them(value) -> None:
    with pytest.raises(ConnectorError) as raised:
        s3.parse_credentials(value)

    assert raised.value.code == ConnectorError.CREDENTIALS_INVALID
    assert "hunter2" not in raised.value.message


def test_registration_builds_a_connector_from_config_and_secret(ctx) -> None:
    connector = s3.REGISTRATION.factory(ctx, {"bucket": "docs"}, SECRET_JSON)

    assert isinstance(connector, s3.S3Connector)
    assert s3.REGISTRATION.descriptor.secret == "required"
    assert {field.key for field in s3.REGISTRATION.descriptor.fields} == {
        "bucket",
        "region",
        "endpoint",
        "prefix",
        "include",
        "exclude",
        "path_style",
    }
