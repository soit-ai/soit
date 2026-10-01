"""Web crawl connector.

Starts from seed URLs and follows links breadth-first, staying on the seeds'
hosts (and, if set, under a path prefix), up to a depth and a page cap. It
reads robots.txt and obeys it, sends no credentials or cookies, accepts HTML,
plain text, Markdown and PDF, and sends conditional requests for pages the
previous sync already saw so unchanged pages cost no download.

Every request, redirect hops included, goes through the governed egress
client; a redirect to another host is not followed.

What "removed" means here: a page the crawl no longer reaches (gone, or no
longer linked within the depth and page limits) is reported as missing. A page
that fails for a transient reason is reported as failed instead, never missing,
and a crawl cut off by the page cap marks the listing incomplete so nothing is
deleted because of it.
"""

from __future__ import annotations

import asyncio
import http.cookiejar
from collections import deque
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import SplitResult, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

from app.adapters.connectors.common import (
    RESOURCE_WEB,
    basename,
    config_int,
    config_string,
    config_string_list,
    guarded,
    make_client,
    read_limited,
    reject_unknown_keys,
    validate_http_url,
)
from app.adapters.connectors.robots import RobotsRules
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
from app.kernel.security.egress import GovernedEgressGuard

KIND = "web"
USER_AGENT = "SOITKnowledgeBot/1.0 (+https://soit.ai)"
AGENT_TOKEN = "soitknowledgebot"
ACCEPT = "text/html,application/xhtml+xml,text/plain,text/markdown,application/pdf;q=0.9,*/*;q=0.1"

DEFAULT_MAX_DEPTH = 2
MAX_DEPTH_CAP = 5
DEFAULT_MAX_PAGES = 50
MAX_PAGES_CAP = 500
MAX_SEEDS = 20
MAX_PAGE_BYTES = 5 * 1024 * 1024
MAX_ROBOTS_BYTES = 512 * 1024
MAX_REDIRECTS = 5
MAX_LINKS_PER_PAGE = 1000
MAX_URL_LENGTH = 1024
MAX_CRAWL_DELAY_SECONDS = 5.0

_HTML = ("text/html", "application/xhtml+xml")
_MARKDOWN = ("text/markdown", "text/x-markdown")
_ACCEPTED = (*_HTML, *_MARKDOWN, "text/plain", "application/pdf")
_FILENAME_SUFFIX = {
    "text/html": ".html",
    "text/markdown": ".md",
    "text/plain": ".txt",
    "application/pdf": ".pdf",
}

_ALLOWED_KEYS = ("seed_urls", "max_depth", "max_pages", "path_prefix")

DESCRIPTOR = ConnectorDescriptor(
    kind=KIND,
    label="Website crawl",
    description=(
        "Crawl a website from seed URLs, following links on the same host. Obeys robots.txt and sends no credentials, "
        "so it reads public pages only."
    ),
    secret="none",
    fields=(
        ConnectorField(
            key="seed_urls",
            label="Seed URLs",
            type="string_list",
            required=True,
            placeholder="https://docs.example.com/",
            help="Where the crawl starts. Links are followed on these URLs' hosts only.",
        ),
        ConnectorField(
            key="path_prefix",
            label="Path prefix",
            placeholder="/docs/",
            help="Only follow links whose path starts with this. Seed URLs are always read.",
        ),
        ConnectorField(
            key="max_depth",
            label="Max depth",
            type="integer",
            default=DEFAULT_MAX_DEPTH,
            minimum=0,
            maximum=MAX_DEPTH_CAP,
            help="How many links away from a seed to follow. 0 reads only the seeds.",
        ),
        ConnectorField(
            key="max_pages",
            label="Max pages",
            type="integer",
            default=DEFAULT_MAX_PAGES,
            minimum=1,
            maximum=MAX_PAGES_CAP,
            help="The most pages one sync visits. A larger site is cut off here and nothing is removed on that run.",
        ),
    ),
)


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize a web source's configuration."""
    reject_unknown_keys(config, _ALLOWED_KEYS)
    seeds = config_string_list(config, "seed_urls", max_items=MAX_SEEDS, max_length=MAX_URL_LENGTH)
    if not seeds:
        raise ConnectorError(ConnectorError.CONFIG_INVALID, "seed_urls needs at least one URL")
    normalized: list[str] = []
    for seed in seeds:
        validate_http_url(seed, key="seed_urls", allow_path=True, allow_query=True)
        url = normalize_url(seed)
        if url is None:
            raise ConnectorError(ConnectorError.CONFIG_INVALID, f"{seed} is not a usable URL")
        if url not in normalized:
            normalized.append(url)
    prefix = config_string(config, "path_prefix", default="", max_length=256) or ""
    if prefix and not prefix.startswith("/"):
        raise ConnectorError(ConnectorError.CONFIG_INVALID, "path_prefix must start with /")
    return {
        "seed_urls": normalized,
        "path_prefix": prefix,
        "max_depth": config_int(config, "max_depth", default=DEFAULT_MAX_DEPTH, minimum=0, maximum=MAX_DEPTH_CAP),
        "max_pages": config_int(config, "max_pages", default=DEFAULT_MAX_PAGES, minimum=1, maximum=MAX_PAGES_CAP),
    }


def validate_credentials(secret_value: str | None) -> None:
    """The crawl takes no credentials; a secret on the source would be ignored, so refuse it."""
    if secret_value:
        raise ConnectorError(
            ConnectorError.CREDENTIALS_INVALID,
            "The web crawl sends no credentials; remove the secret from this source",
        )


def normalize_url(url: str) -> str | None:
    """A canonical form for deduplication: lowercase host, no fragment, no default port."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 443 if parts.scheme == "https" else 80
    netloc = host if port in (None, default_port) else f"{host}:{port}"
    path = parts.path or "/"
    result = urlunsplit((parts.scheme, netloc, path, parts.query, ""))
    return result if len(result) <= MAX_URL_LENGTH else None


def _host_key(parts: SplitResult) -> str:
    """Hostname and effective port, so a different port counts as a different site."""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return f"{(parts.hostname or '').lower()}:{port}"


def _media_type(content_type: str | None) -> str:
    return (content_type or "").split(";", 1)[0].strip().lower()


@dataclass
class _Page:
    """The outcome of asking for one URL."""

    kind: str
    """ok, not_modified, gone, blocked, offsite, unsupported"""

    url: str
    body: bytes = b""
    media_type: str = ""
    etag: str | None = None
    modified: str | None = None


def build_client(ctx: RequestContext, *, egress_guard: GovernedEgressGuard | None = None, **kwargs: Any) -> httpx.AsyncClient:
    """The crawl's HTTP client: egress-governed, identifying itself, and cookie-less."""
    headers = {"User-Agent": USER_AGENT, **dict(kwargs.pop("headers", {}) or {})}
    client = make_client(ctx, RESOURCE_WEB, egress_guard=egress_guard, headers=headers, **kwargs)
    # The crawl is anonymous: a cookie a site sets must not come back on later
    # requests.
    client.cookies.jar.set_policy(http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))
    return client


class WebConnector:
    """One configured crawl."""

    def __init__(
        self,
        ctx: RequestContext,
        config: Mapping[str, Any],
        *,
        client_factory: Callable[[], httpx.AsyncClient] | None = None,
        sleep: Callable[[float], Any] = asyncio.sleep,
    ) -> None:
        self.seeds: list[str] = list(config["seed_urls"])
        self.path_prefix: str = config.get("path_prefix") or ""
        self.max_depth: int = int(config.get("max_depth", DEFAULT_MAX_DEPTH))
        self.max_pages: int = int(config.get("max_pages", DEFAULT_MAX_PAGES))
        self._hosts = {_host_key(urlsplit(seed)) for seed in self.seeds}
        self._client_factory = client_factory or (lambda: build_client(ctx))
        self._sleep = sleep
        self._robots: dict[str, RobotsRules] = {}
        self._last_request: dict[str, float] = {}
        self._bodies: dict[str, _Page] = {}
        self._skipped = 0
        self._incomplete = 0

    # ------------------------------------------------------------- robots

    async def _rules_for(self, client: httpx.AsyncClient, url: str) -> RobotsRules:
        parts = urlsplit(url)
        key = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(key)
        if cached is not None:
            return cached
        robots_url = f"{key}/robots.txt"

        async def call() -> RobotsRules:
            response = await client.send(
                client.build_request("GET", robots_url, headers={"Accept": "text/plain"}), stream=True
            )
            try:
                status = response.status_code
                if status == 200:
                    body = await read_limited(response, MAX_ROBOTS_BYTES)
                    return RobotsRules.parse(body.decode("utf-8", errors="replace"), agent=AGENT_TOKEN)
                if 400 <= status < 500:
                    # No usable robots.txt: nothing is disallowed.
                    return RobotsRules.allow_all()
                # A server error means the rules cannot be known; stay out.
                return RobotsRules.disallow_all()
            finally:
                await response.aclose()

        try:
            rules = await guarded(call, host=parts.netloc)
        except ConnectorError as exc:
            if exc.code == ConnectorError.EGRESS_BLOCKED:
                raise
            rules = RobotsRules.disallow_all()
        self._robots[key] = rules
        return rules

    async def _throttle(self, host: str, rules: RobotsRules) -> None:
        delay = min(rules.crawl_delay or 0.0, MAX_CRAWL_DELAY_SECONDS)
        if delay <= 0:
            return
        loop = asyncio.get_running_loop()
        last = self._last_request.get(host)
        now = loop.time()
        if last is not None and now - last < delay:
            await self._sleep(delay - (now - last))
        self._last_request[host] = loop.time()

    # -------------------------------------------------------------- fetch

    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        known: KnownItem | None,
    ) -> _Page:
        current = url
        for _hop in range(MAX_REDIRECTS + 1):
            parts = urlsplit(current)
            rules = await self._rules_for(client, current)
            target = parts.path + (f"?{parts.query}" if parts.query else "")
            if not rules.allows(target or "/"):
                return _Page("blocked", current)
            await self._throttle(parts.netloc, rules)

            headers = {"Accept": ACCEPT}
            if known is not None and current == url:
                if known.etag:
                    headers["If-None-Match"] = known.etag
                if known.modified:
                    headers["If-Modified-Since"] = known.modified

            async def call(target_url: str = current, request_headers: dict[str, str] = headers) -> _Page:
                response = await client.send(client.build_request("GET", target_url, headers=request_headers), stream=True)
                try:
                    return await self._read_response(response, target_url)
                finally:
                    await response.aclose()

            page = await guarded(call, host=parts.netloc)
            if page.kind != "redirect":
                return page
            current = page.url
        raise ConnectorError(ConnectorError.ITEM_FAILED, "The page redirects too many times")

    async def _read_response(self, response: httpx.Response, url: str) -> _Page:
        status = response.status_code
        if status == 304:
            return _Page("not_modified", url)
        if response.is_redirect:
            location = response.headers.get("location")
            target = normalize_url(urljoin(url, location)) if location else None
            if target is None:
                raise ConnectorError(ConnectorError.ITEM_FAILED, "The page redirects somewhere unusable")
            if _host_key(urlsplit(target)) not in self._hosts:
                return _Page("offsite", target)
            return _Page("redirect", target)
        if status in (404, 410):
            return _Page("gone", url)
        if status >= 400:
            raise ConnectorError(ConnectorError.ITEM_FAILED, f"The server answered {status}")
        media = _media_type(response.headers.get("content-type"))
        if media not in _ACCEPTED:
            return _Page("unsupported", url, media_type=media)
        body = await read_limited(response, MAX_PAGE_BYTES)
        return _Page(
            "ok",
            url,
            body=body,
            media_type=media,
            etag=response.headers.get("etag"),
            modified=response.headers.get("last-modified"),
        )

    # -------------------------------------------------------------- links

    def _follows(self, url: str) -> bool:
        parts = urlsplit(url)
        if _host_key(parts) not in self._hosts:
            return False
        return not self.path_prefix or parts.path.startswith(self.path_prefix)

    def _discover(self, page_url: str, soup: BeautifulSoup) -> list[str]:
        base = page_url
        base_tag = soup.find("base", href=True)
        if base_tag is not None:
            base = urljoin(page_url, str(base_tag["href"]))
        found: list[str] = []
        for anchor in soup.find_all("a", href=True):
            if len(found) >= MAX_LINKS_PER_PAGE:
                break
            raw_rel: Any = anchor.get("rel") or []
            rel_values: list[Any] = raw_rel.split() if isinstance(raw_rel, str) else list(raw_rel)
            if "nofollow" in [str(value).lower() for value in rel_values]:
                continue
            target = normalize_url(urljoin(base, str(anchor["href"])))
            if target and self._follows(target) and target not in found:
                found.append(target)
        return found

    @staticmethod
    def _meta_robots(soup: BeautifulSoup) -> set[str]:
        tag = soup.find("meta", attrs={"name": lambda value: bool(value) and str(value).lower() in ("robots", AGENT_TOKEN)})
        if tag is None:
            return set()
        content = str(tag.get("content") or "").lower()
        return {part.strip() for part in content.split(",") if part.strip()}

    # ---------------------------------------------------------------- crawl

    async def _crawl(
        self,
        known: Mapping[str, KnownItem],
        *,
        max_pages: int,
    ) -> AsyncIterator[ConnectorItem]:
        self._skipped = 0
        self._incomplete = 0
        self._bodies.clear()
        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque((seed, 0) for seed in self.seeds)
        seeds = set(self.seeds)
        attempts = 0

        async with self._client_factory() as client:
            while queue:
                url, depth = queue.popleft()
                if url in seen:
                    continue
                if attempts >= max_pages:
                    # Pages are left unvisited, so what was not seen proves nothing.
                    self._incomplete = 1
                    return
                seen.add(url)
                attempts += 1
                is_seed = url in seeds

                try:
                    page = await self._fetch_page(client, url, known.get(url))
                except ConnectorError as exc:
                    if is_seed or exc.code == ConnectorError.EGRESS_BLOCKED:
                        raise ConnectorError(
                            ConnectorError.EGRESS_BLOCKED if exc.code == ConnectorError.EGRESS_BLOCKED
                            else ConnectorError.LISTING_FAILED,
                            f"{url}: {exc.message}",
                        ) from exc
                    yield ConnectorItem(external_id=url, name=basename(url), source_uri=url, error=exc.message)
                    continue

                if page.kind == "gone":
                    if is_seed:
                        raise ConnectorError(ConnectorError.LISTING_FAILED, f"The seed URL {url} was not found")
                    continue
                if page.kind in ("blocked", "offsite", "unsupported"):
                    if is_seed:
                        reason = {
                            "blocked": "is disallowed by the site's robots.txt",
                            "offsite": "redirects to another host",
                            "unsupported": f"is not a supported content type ({page.media_type or 'unknown'})",
                        }[page.kind]
                        raise ConnectorError(ConnectorError.LISTING_FAILED, f"The seed URL {url} {reason}")
                    self._skipped += 1
                    continue

                if page.kind == "not_modified":
                    previous = known.get(url)
                    if previous is None:
                        yield ConnectorItem(
                            external_id=url,
                            name=basename(url),
                            source_uri=url,
                            error="The server answered 304 to a request that was not conditional",
                        )
                        continue
                    stored_links: list[Any] = list(previous.meta.get("links") or [])
                    links = [str(link) for link in stored_links]
                    if depth < self.max_depth and not previous.meta.get("nofollow"):
                        self._enqueue(queue, seen, links, depth + 1)
                    yield ConnectorItem(
                        external_id=url,
                        name=str(previous.meta.get("title") or basename(url)),
                        source_uri=url,
                        etag=previous.etag,
                        modified=previous.modified,
                        meta=dict(previous.meta),
                    )
                    continue

                final_url = page.url
                if final_url != url:
                    if final_url in seen:
                        continue
                    seen.add(final_url)

                title: str | None = None
                links: list[str] = []
                nofollow = False
                if page.media_type in _HTML:
                    soup = BeautifulSoup(page.body, "html.parser")
                    directives = self._meta_robots(soup)
                    if "noindex" in directives and not is_seed:
                        self._skipped += 1
                        continue
                    nofollow = "nofollow" in directives
                    if soup.title is not None and soup.title.string:
                        title = " ".join(soup.title.string.split())[:300] or None
                    if not nofollow:
                        links = self._discover(final_url, soup)
                if depth < self.max_depth and links:
                    self._enqueue(queue, seen, links, depth + 1)

                meta: dict[str, Any] = {"links": links, "nofollow": nofollow}
                if title:
                    meta["title"] = title
                self._bodies[final_url] = page
                yield ConnectorItem(
                    external_id=final_url,
                    name=title or basename(final_url),
                    source_uri=final_url,
                    etag=page.etag,
                    modified=page.modified,
                    size=len(page.body),
                    content_type=_canonical_type(page.media_type),
                    meta=meta,
                )

    @staticmethod
    def _enqueue(queue: deque[tuple[str, int]], seen: set[str], links: list[str], depth: int) -> None:
        for link in links:
            if link not in seen:
                queue.append((link, depth))

    def iter_items(self, known: Mapping[str, KnownItem]) -> AsyncIterator[ConnectorItem]:
        """Every page the crawl reaches."""
        return self._crawl(known, max_pages=self.max_pages)

    async def fetch_item(self, item: ConnectorItem, *, max_bytes: int) -> FetchedItem:
        """The page's content, from the crawl that just read it where possible."""
        page = self._bodies.pop(item.external_id, None)
        if page is None:
            async with self._client_factory() as client:
                page = await self._fetch_page(client, item.external_id, None)
            if page.kind != "ok":
                raise ConnectorError(ConnectorError.ITEM_FAILED, f"The page could not be read ({page.kind})")
        if len(page.body) > max_bytes:
            raise ConnectorError(
                ConnectorError.ITEM_TOO_LARGE,
                f"The page is {len(page.body)} bytes, over the {max_bytes} byte limit",
            )
        content_type = _canonical_type(page.media_type)
        title = item.meta.get("title") if item.meta else None
        return FetchedItem(
            content=page.body,
            content_type=content_type,
            filename=_filename(item.external_id, content_type),
            title=str(title) if title else None,
            etag=page.etag,
            modified=page.modified,
        )

    async def test_connection(self, *, sample_size: int = 10) -> ConnectionReport:
        sample: list[ConnectorItem] = []
        failed = 0
        try:
            async for item in self._crawl({}, max_pages=max(1, min(sample_size, self.max_pages))):
                if item.error:
                    failed += 1
                    continue
                sample.append(item)
        except ConnectorError as exc:
            return ConnectionReport(ok=False, message=exc.message)
        finally:
            self._bodies.clear()
        if not sample:
            return ConnectionReport(ok=False, message="No readable pages were found from the seed URLs")
        note = f"; {failed} could not be read" if failed else ""
        return ConnectionReport(
            ok=True,
            message=f"Read {len(sample)} pages from {len(self.seeds)} seed URL(s){note}",
            sample=tuple(sample[:sample_size]),
        )

    def stats(self) -> Mapping[str, int]:
        return {"skipped": self._skipped, "incomplete": self._incomplete}


def _canonical_type(media_type: str) -> str:
    if media_type in _HTML:
        return "text/html"
    if media_type in _MARKDOWN:
        return "text/markdown"
    return media_type or "text/plain"


def _filename(url: str, content_type: str) -> str:
    """A file name whose extension matches the content, which parsers rely on."""
    path = urlsplit(url).path
    name = basename(path) if path.strip("/") else "index"
    suffix = _FILENAME_SUFFIX.get(content_type, "")
    lowered = name.lower()
    known_suffixes = {
        "text/html": (".html", ".htm", ".xhtml"),
        "text/markdown": (".md", ".markdown"),
        "text/plain": (".txt", ".text"),
        "application/pdf": (".pdf",),
    }.get(content_type, ())
    if suffix and not lowered.endswith(known_suffixes):
        name = f"{name}{suffix}"
    return name


def _factory(ctx: RequestContext, config: Mapping[str, Any], secret_value: str | None) -> WebConnector:
    validate_credentials(secret_value)
    return WebConnector(ctx, validate_config(config))


REGISTRATION = ConnectorRegistration(
    descriptor=DESCRIPTOR,
    validate_config=validate_config,
    validate_credentials=validate_credentials,
    factory=_factory,
)

__all__ = ["DESCRIPTOR", "KIND", "REGISTRATION", "WebConnector", "normalize_url", "validate_config"]
