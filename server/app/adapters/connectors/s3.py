"""S3-compatible object storage connector (AWS S3, MinIO, Cloudflare R2, ...).

Lists a bucket (optionally under a prefix) with ListObjectsV2 and downloads
objects with GetObject, both signed with Signature Version 4 and sent through
the governed egress client. Credentials come from a secret holding JSON
``{"access_key_id": ..., "secret_access_key": ..., "session_token": ...}``;
they are used to sign requests and never leave this module.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator, Callable, Mapping
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlsplit

import httpx

from app.adapters.connectors import sigv4
from app.adapters.connectors.common import (
    RESOURCE_S3,
    basename,
    config_bool,
    config_string,
    config_string_list,
    content_type_for,
    guarded,
    make_client,
    matches_any,
    read_limited,
    reject_unknown_keys,
    validate_http_url,
)
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.connectors import (
    ConnectionReport,
    ConnectorDescriptor,
    ConnectorError,
    ConnectorField,
    ConnectorItem,
    ConnectorRegistration,
    FetchedItem,
    KnownItem,
)

KIND = "s3"
LIST_PAGE_SIZE = 1000
MAX_LIST_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_SCANNED_OBJECTS = 500_000
"""Objects examined (listed, whether kept or not) before a listing gives up.

A bucket with far more objects than the sync could ever take is better refused
with a pointer to the prefix setting than walked for hours; ending the listing
quietly instead would make every unseen object look removed.
"""

_ALLOWED_KEYS = ("endpoint", "region", "bucket", "prefix", "include", "exclude", "path_style")

DESCRIPTOR = ConnectorDescriptor(
    kind=KIND,
    label="S3-compatible storage",
    description="Sync documents from an AWS S3, MinIO, Cloudflare R2 or other S3-compatible bucket.",
    secret="required",
    secret_help='A secret whose value is JSON: {"access_key_id": "...", "secret_access_key": "...", '
    '"session_token": "..."}. The session token is optional.',
    fields=(
        ConnectorField(key="bucket", label="Bucket", required=True, placeholder="my-docs"),
        ConnectorField(
            key="region",
            label="Region",
            default="us-east-1",
            help="The bucket's region. Many S3-compatible services accept any value, such as us-east-1.",
        ),
        ConnectorField(
            key="endpoint",
            label="Endpoint",
            placeholder="https://minio.example.com:9000",
            help="Leave empty for AWS S3. Set it for MinIO, R2 and other S3-compatible services.",
        ),
        ConnectorField(
            key="prefix",
            label="Prefix",
            placeholder="handbook/",
            help="Only objects whose key starts with this are synced.",
        ),
        ConnectorField(
            key="include",
            label="Include patterns",
            type="string_list",
            placeholder="*.pdf",
            help="Only keys matching one of these patterns are synced. * matches any characters, including /.",
        ),
        ConnectorField(
            key="exclude",
            label="Exclude patterns",
            type="string_list",
            placeholder="drafts/*",
            help="Keys matching one of these patterns are skipped.",
        ),
        ConnectorField(
            key="path_style",
            label="Path-style addressing",
            type="boolean",
            help="Use endpoint/bucket/key instead of bucket.endpoint/key. Defaults to on when an endpoint is set.",
        ),
    ),
)


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize an S3 source's configuration."""
    reject_unknown_keys(config, _ALLOWED_KEYS)
    bucket = config_string(config, "bucket", required=True, max_length=63) or ""
    if not (3 <= len(bucket) <= 63) or not all(ch.isalnum() or ch in ".-_" for ch in bucket):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, "bucket is not a valid bucket name")
    region = config_string(config, "region", default="us-east-1", max_length=32) or "us-east-1"
    if not all(ch.isalnum() or ch == "-" for ch in region):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, "region is not a valid region name")
    endpoint = config_string(config, "endpoint", max_length=512)
    if endpoint:
        endpoint = validate_http_url(endpoint, key="endpoint", allow_path=False)
    prefix = (config_string(config, "prefix", default="", max_length=512) or "").lstrip("/")
    path_style = config_bool(config, "path_style", default=bool(endpoint))
    return {
        "bucket": bucket,
        "region": region,
        "endpoint": endpoint,
        "prefix": prefix,
        "include": config_string_list(config, "include"),
        "exclude": config_string_list(config, "exclude"),
        "path_style": path_style,
    }


def parse_credentials(secret_value: str | None) -> sigv4.AwsCredentials:
    """Read the secret's JSON without ever repeating any of it in an error."""
    if not secret_value:
        raise ConnectorError(ConnectorError.CREDENTIALS_INVALID, "This connector needs a secret with credentials")
    data: Any
    try:
        data = json.loads(secret_value)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise ConnectorError(
            ConnectorError.CREDENTIALS_INVALID,
            "The secret must be JSON with access_key_id and secret_access_key",
        )
    fields = cast("dict[str, Any]", data)
    access_key = fields.get("access_key_id")
    secret_key = fields.get("secret_access_key")
    token = fields.get("session_token")
    if not isinstance(access_key, str) or not access_key or not isinstance(secret_key, str) or not secret_key:
        raise ConnectorError(
            ConnectorError.CREDENTIALS_INVALID,
            "The secret must contain access_key_id and secret_access_key",
        )
    if token is not None and not isinstance(token, str):
        raise ConnectorError(ConnectorError.CREDENTIALS_INVALID, "session_token must be text")
    return sigv4.AwsCredentials(access_key, secret_key, token or None)


def validate_credentials(secret_value: str | None) -> None:
    parse_credentials(secret_value)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == name:
            return (child.text or "").strip()
    return None


def _error_summary(body: bytes) -> str | None:
    """The code and message of an S3 error document, if the body is one."""
    try:
        root = ET.fromstring(body[:16384])
    except ET.ParseError:
        return None
    code = _child_text(root, "Code")
    message = _child_text(root, "Message")
    if not code:
        return None
    return f"{code}: {message}" if message else code


class S3Connector:
    """One configured S3-compatible bucket."""

    def __init__(
        self,
        ctx: RequestContext,
        config: Mapping[str, Any],
        credentials: sigv4.AwsCredentials,
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.bucket: str = config["bucket"]
        self.region: str = config.get("region") or "us-east-1"
        self.endpoint: str | None = config.get("endpoint") or None
        self.prefix: str = config.get("prefix") or ""
        self.include: list[str] = list(config.get("include") or [])
        self.exclude: list[str] = list(config.get("exclude") or [])
        self.path_style: bool = bool(config.get("path_style", bool(self.endpoint)))
        # Dots in a bucket name break the wildcard certificate of virtual-hosted
        # addressing, so such buckets are always addressed by path.
        if "." in self.bucket:
            self.path_style = True
        self._credentials = credentials
        self._client_factory = client_factory or (lambda: make_client(ctx, RESOURCE_S3))
        self._clock = clock
        self._skipped = 0

    # ---------------------------------------------------------------- urls

    def _base(self) -> tuple[str, str, str]:
        """(scheme, host, path prefix) objects are addressed under."""
        if self.endpoint:
            parts = urlsplit(self.endpoint)
            scheme, netloc = parts.scheme, parts.netloc
        else:
            scheme = "https"
            netloc = f"s3.{self.region}.amazonaws.com" if self.region != "us-east-1" else "s3.amazonaws.com"
        if self.path_style:
            return scheme, netloc, f"/{self.bucket}"
        return scheme, f"{self.bucket}.{netloc}", ""

    def _url(self, key: str | None, query: list[tuple[str, str]] | None = None) -> str:
        scheme, host, base = self._base()
        path = f"{base}/{sigv4.encode_path(key)}" if key is not None else f"{base}/"
        url = f"{scheme}://{host}{path}"
        if query:
            url += "?" + sigv4.canonical_query(query)
        return url

    def _host(self) -> str:
        return self._base()[1]

    # ------------------------------------------------------------ requests

    async def _get(self, client: httpx.AsyncClient, url: str, *, max_bytes: int, stream_label: str) -> bytes:
        request = client.build_request("GET", url)
        signed = sigv4.sign_get(
            url=str(request.url),
            credentials=self._credentials,
            region=self.region,
            now=self._clock(),
        )
        request.headers.update(signed)

        async def call() -> bytes:
            response = await client.send(request, stream=True)
            try:
                if response.status_code != 200:
                    body = await read_limited(response, 64 * 1024) if response.status_code >= 400 else b""
                    raise self._http_error(response, body, stream_label)
                return await read_limited(response, max_bytes)
            finally:
                await response.aclose()

        return await guarded(call, host=self._host())

    def _http_error(self, response: httpx.Response, body: bytes, label: str) -> ConnectorError:
        status = response.status_code
        detail = _error_summary(body)
        suffix = f" ({detail})" if detail else ""
        if status in (301, 307, 400) and response.headers.get("x-amz-bucket-region"):
            region = response.headers["x-amz-bucket-region"]
            return ConnectorError(
                ConnectorError.LISTING_FAILED if label == "list" else ConnectorError.ITEM_FAILED,
                f"The bucket is in region {region}; set the region on the source{suffix}",
            )
        if status in (401, 403):
            return ConnectorError(
                ConnectorError.AUTH_FAILED if label == "list" else ConnectorError.ITEM_FAILED,
                f"The storage service refused the credentials or the request ({status}){suffix}",
            )
        if status == 404:
            return ConnectorError(
                ConnectorError.LISTING_FAILED if label == "list" else ConnectorError.ITEM_FAILED,
                ("The bucket was not found" if label == "list" else "The object no longer exists") + suffix,
            )
        return ConnectorError(
            ConnectorError.LISTING_FAILED if label == "list" else ConnectorError.ITEM_FAILED,
            f"The storage service answered {status}{suffix}",
        )

    # ------------------------------------------------------------- listing

    def _parse_page(self, body: bytes) -> tuple[list[ConnectorItem], str | None, int]:
        """Items kept from one ListObjectsV2 page, the next token, and objects examined."""
        if b"<!DOCTYPE" in body[:2048].upper() or b"<!ENTITY" in body[:4096].upper():
            raise ConnectorError(ConnectorError.LISTING_FAILED, "The listing response is not valid S3 XML")
        try:
            root = ET.fromstring(body)
        except ET.ParseError as exc:
            raise ConnectorError(ConnectorError.LISTING_FAILED, "The listing response is not valid S3 XML") from exc
        if _local_name(root.tag) != "ListBucketResult":
            raise ConnectorError(
                ConnectorError.LISTING_FAILED,
                "The endpoint did not answer like an S3 service; check the endpoint and path-style setting",
            )
        items: list[ConnectorItem] = []
        examined = 0
        for contents in root:
            if _local_name(contents.tag) != "Contents":
                continue
            examined += 1
            key = _child_text(contents, "Key")
            if not key:
                continue
            item = self._item_for(
                key,
                etag=(_child_text(contents, "ETag") or "").strip('"') or None,
                modified=_child_text(contents, "LastModified"),
                size_text=_child_text(contents, "Size"),
            )
            if item is not None:
                items.append(item)
        truncated = (_child_text(root, "IsTruncated") or "").lower() == "true"
        token = _child_text(root, "NextContinuationToken") if truncated else None
        if truncated and not token:
            raise ConnectorError(ConnectorError.LISTING_FAILED, "The listing was cut off without a continuation token")
        return items, token, examined

    def _item_for(self, key: str, *, etag: str | None, modified: str | None, size_text: str | None) -> ConnectorItem | None:
        if key.endswith("/"):
            # A folder placeholder, not a document.
            self._skipped += 1
            return None
        content_type = content_type_for(key)
        if content_type is None:
            self._skipped += 1
            return None
        if self.include and not matches_any(key, self.include):
            self._skipped += 1
            return None
        if self.exclude and matches_any(key, self.exclude):
            self._skipped += 1
            return None
        size = int(size_text) if size_text and size_text.isdigit() else None
        return ConnectorItem(
            external_id=key,
            name=basename(key),
            source_uri=f"s3://{self.bucket}/{key}",
            etag=etag,
            modified=modified,
            size=size,
            content_type=content_type,
        )

    async def _list_page(
        self, client: httpx.AsyncClient, token: str | None, *, max_keys: int = LIST_PAGE_SIZE
    ) -> tuple[list[ConnectorItem], str | None, int]:
        query = [("list-type", "2"), ("max-keys", str(max_keys))]
        if self.prefix:
            query.append(("prefix", self.prefix))
        if token:
            query.append(("continuation-token", token))
        body = await self._get(client, self._url(None, query), max_bytes=MAX_LIST_RESPONSE_BYTES, stream_label="list")
        return self._parse_page(body)

    async def iter_items(self, known: Mapping[str, KnownItem]) -> AsyncIterator[ConnectorItem]:
        """Every supported object under the prefix."""
        self._skipped = 0
        scanned = 0
        token: str | None = None
        async with self._client_factory() as client:
            while True:
                items, token, examined = await self._list_page(client, token)
                scanned += examined
                for item in items:
                    yield item
                if token is None:
                    return
                if scanned >= MAX_SCANNED_OBJECTS:
                    raise ConnectorError(
                        ConnectorError.LISTING_FAILED,
                        f"The bucket holds more than {MAX_SCANNED_OBJECTS} objects under this prefix; "
                        "narrow the prefix or the include patterns",
                    )

    async def fetch_item(self, item: ConnectorItem, *, max_bytes: int) -> FetchedItem:
        """Download one object."""
        async with self._client_factory() as client:
            content = await self._get(client, self._url(item.external_id), max_bytes=max_bytes, stream_label="object")
        return FetchedItem(
            content=content,
            content_type=item.content_type or content_type_for(item.external_id) or "text/plain",
            filename=basename(item.external_id),
            etag=item.etag,
            modified=item.modified,
        )

    async def test_connection(self, *, sample_size: int = 10) -> ConnectionReport:
        self._skipped = 0
        try:
            async with self._client_factory() as client:
                items, token, _examined = await self._list_page(client, None, max_keys=max(1, min(sample_size * 5, 200)))
        except ConnectorError as exc:
            return ConnectionReport(ok=False, message=exc.message)
        sample = tuple(items[:sample_size])
        more = " (more objects follow)" if token or len(items) > len(sample) else ""
        message = f"Connected to bucket {self.bucket}; {len(sample)} matching objects in the sample{more}"
        if not sample:
            message = (
                f"Connected to bucket {self.bucket}, but no matching objects were found in the first page. "
                "Check the prefix and patterns"
            )
        return ConnectionReport(ok=True, message=message, sample=sample)

    def stats(self) -> Mapping[str, int]:
        return {"skipped": self._skipped}


def _factory(ctx: RequestContext, config: Mapping[str, Any], secret_value: str | None) -> S3Connector:
    return S3Connector(ctx, validate_config(config), parse_credentials(secret_value))


REGISTRATION = ConnectorRegistration(
    descriptor=DESCRIPTOR,
    validate_config=validate_config,
    validate_credentials=validate_credentials,
    factory=_factory,
)

__all__ = ["DESCRIPTOR", "KIND", "REGISTRATION", "S3Connector", "parse_credentials", "validate_config"]
