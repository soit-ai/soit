"""Web crawl connector: crawl rules, robots.txt, conditional requests, egress."""

from __future__ import annotations

import httpx
import pytest

from app.adapters.connectors import web
from app.adapters.connectors.robots import RobotsRules
from app.kernel.ports.connectors import ConnectorError, ConnectorItem, KnownItem
from app.kernel.security import egress
from app.kernel.security.egress import GovernedEgressGuard
from app.settings.settings import settings

HOST = "docs.example.com"


class PublicResolver:
    def __init__(self, address: str = "93.184.216.34") -> None:
        self.address = address

    async def resolve(self, hostname: str, port: int) -> list[str]:
        return [self.address]


@pytest.fixture(autouse=True)
def egress_policy(monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["*.example.com", "example.com", "other.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(settings, "egress_private_networks", [])
    monkeypatch.setattr(egress, "_egress_policy", None)


def html(title: str = "Page", *links: str, head: str = "", body: str = "") -> str:
    anchors = "".join(f'<a href="{link}">link</a>' for link in links)
    return f"<html><head><title>{title}</title>{head}</head><body><p>{title} content</p>{anchors}{body}</body></html>"


class Site:
    """A fake website keyed by host and path."""

    def __init__(self) -> None:
        self.pages: dict[str, tuple[int, dict[str, str], bytes]] = {}
        self.requests: list[httpx.Request] = []

    def add(
        self,
        path: str,
        body: str | bytes = "",
        *,
        host: str = HOST,
        status: int = 200,
        content_type: str | None = "text/html; charset=utf-8",
        headers: dict[str, str] | None = None,
    ) -> None:
        merged = dict(headers or {})
        if content_type:
            merged["content-type"] = content_type
        self.pages[f"{host}{path}"] = (status, merged, body.encode() if isinstance(body, str) else body)

    def robots(self, text: str, *, host: str = HOST, status: int = 200) -> None:
        self.add("/robots.txt", text, host=host, status=status, content_type="text/plain")

    def fetched(self, path: str, host: str = HOST) -> int:
        return len([r for r in self.requests if r.url.host == host and r.url.raw_path.decode() == path])

    def paths(self, host: str = HOST) -> list[str]:
        return [r.url.raw_path.decode() for r in self.requests if r.url.host == host and r.url.path != "/robots.txt"]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = f"{request.url.host}{request.url.raw_path.decode()}"
        if key not in self.pages:
            return httpx.Response(404, content=b"not found")
        status, headers, body = self.pages[key]
        conditional = request.headers.get("if-none-match")
        if conditional and headers.get("etag") == conditional:
            return httpx.Response(304, headers={"etag": conditional})
        return httpx.Response(status, headers=headers, content=body)


def connector(ctx, site: Site, **config) -> web.WebConnector:
    config.setdefault("seed_urls", [f"https://{HOST}/"])
    normalized = web.validate_config(config)
    guard = GovernedEgressGuard(address_resolver=PublicResolver())
    return web.WebConnector(
        ctx,
        normalized,
        client_factory=lambda: web.build_client(ctx, egress_guard=guard, transport=httpx.MockTransport(site)),
        sleep=_no_sleep,
    )


async def _no_sleep(_seconds: float) -> None:
    return None


async def crawl(conn: web.WebConnector, known: dict[str, KnownItem] | None = None) -> list[ConnectorItem]:
    return [item async for item in conn.iter_items(known or {})]


def ids(items: list[ConnectorItem]) -> list[str]:
    return [item.external_id for item in items]


# ------------------------------------------------------------------ robots


def test_robots_default_allows_everything() -> None:
    rules = RobotsRules.parse("", agent="soitknowledgebot")

    assert rules.allows("/anything")


def test_robots_longest_match_wins_and_allow_wins_a_tie() -> None:
    rules = RobotsRules.parse(
        "User-agent: *\nDisallow: /private/\nAllow: /private/public/\nDisallow: /tie\nAllow: /tie\n",
        agent="soitknowledgebot",
    )

    assert not rules.allows("/private/secret.html")
    assert rules.allows("/private/public/page.html")
    assert rules.allows("/tie")
    assert rules.allows("/other")


def test_robots_wildcards_and_end_anchor() -> None:
    rules = RobotsRules.parse(
        "User-agent: *\nDisallow: /*.pdf$\nDisallow: /search?*q=\nDisallow: /tmp*cache\n",
        agent="soitknowledgebot",
    )

    assert not rules.allows("/files/report.pdf")
    assert rules.allows("/files/report.pdf.html")
    assert not rules.allows("/search?page=2&q=term")
    assert rules.allows("/search?page=2")
    assert not rules.allows("/tmp/x/cache")


def test_robots_specific_group_replaces_the_star_group() -> None:
    text = (
        "User-agent: *\nDisallow: /\n\n"
        "User-agent: SOITKnowledgeBot\nDisallow: /admin/\n"
    )
    rules = RobotsRules.parse(text, agent="soitknowledgebot")

    assert rules.allows("/docs/")
    assert not rules.allows("/admin/panel")


def test_robots_consecutive_user_agents_share_one_group_and_comments_are_ignored() -> None:
    text = "User-agent: googlebot # a comment\nUser-agent: soitknowledgebot\nDisallow: /x # why\nCrawl-delay: 3\n"
    rules = RobotsRules.parse(text, agent="soitknowledgebot")

    assert not rules.allows("/x/y")
    assert rules.crawl_delay == 3


def test_robots_empty_disallow_allows_everything() -> None:
    rules = RobotsRules.parse("User-agent: *\nDisallow:\n", agent="soitknowledgebot")

    assert rules.allows("/")


# ------------------------------------------------------------------ config


def test_config_defaults_and_normalization() -> None:
    config = web.validate_config({"seed_urls": ["HTTPS://Docs.Example.com:443/Guide#top", "https://docs.example.com/Guide"]})

    assert config == {
        "seed_urls": ["https://docs.example.com/Guide"],
        "path_prefix": "",
        "max_depth": 2,
        "max_pages": 50,
    }


@pytest.mark.parametrize(
    ("config", "message"),
    [
        ({}, "at least one URL"),
        ({"seed_urls": []}, "at least one URL"),
        ({"seed_urls": ["ftp://x.example.com"]}, "http or https"),
        ({"seed_urls": ["https://user:pw@x.example.com"]}, "credentials"),
        ({"seed_urls": ["https://x.example.com"], "max_depth": 6}, "between 0 and 5"),
        ({"seed_urls": ["https://x.example.com"], "max_pages": 501}, "between 1 and 500"),
        ({"seed_urls": ["https://x.example.com"], "max_pages": 0}, "between 1 and 500"),
        ({"seed_urls": ["https://x.example.com"], "max_depth": "2"}, "whole number"),
        ({"seed_urls": ["https://x.example.com"], "path_prefix": "docs"}, "start with /"),
        ({"seed_urls": ["https://x.example.com"], "headers": {}}, "Unknown setting"),
        ({"seed_urls": ["https://x.example.com"], "token": "abc"}, "looks like a credential"),
        ({"seed_urls": [f"https://x.example.com/{i}" for i in range(21)]}, "at most 20"),
    ],
)
def test_invalid_config_is_rejected(config, message) -> None:
    with pytest.raises(ConnectorError) as raised:
        web.validate_config(config)

    assert message in raised.value.message


def test_a_secret_on_a_web_source_is_refused() -> None:
    web.validate_credentials(None)
    with pytest.raises(ConnectorError) as raised:
        web.validate_credentials("anything")

    assert "hunter2" not in raised.value.message


def test_url_normalization() -> None:
    assert web.normalize_url("HTTP://Example.COM:80/a/b?x=1#frag") == "http://example.com/a/b?x=1"
    assert web.normalize_url("https://example.com") == "https://example.com/"
    assert web.normalize_url("https://example.com:8443/") == "https://example.com:8443/"
    assert web.normalize_url("mailto:a@b.c") is None
    assert web.normalize_url("javascript:void(0)") is None


# ------------------------------------------------------------------- crawl


@pytest.mark.asyncio
async def test_breadth_first_crawl_respects_depth_host_and_dedup(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a", "/b", "/a#section", f"https://{HOST}:443/a", "https://other.com/x", "mailto:x@y.z", "/img.png"))
    site.add("/a", html("A", "/c", "/"))
    site.add("/b", html("B"))
    site.add("/c", html("C", "/d"))
    site.add("/d", html("D"))
    site.add("/img.png", b"\x89PNG", content_type="image/png")
    conn = connector(ctx, site, max_depth=2)

    items = await crawl(conn)

    assert ids(items) == [f"https://{HOST}/", f"https://{HOST}/a", f"https://{HOST}/b", f"https://{HOST}/c"]
    assert site.fetched("/a") == 1
    assert site.paths("other.com") == []
    assert site.fetched("/d") == 0
    assert conn.stats()["skipped"] == 1
    assert conn.stats()["incomplete"] == 0
    assert items[0].name == "Home" and items[0].content_type == "text/html"


@pytest.mark.asyncio
async def test_depth_zero_reads_only_the_seeds(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a"))
    site.add("/a", html("A"))

    items = await crawl(connector(ctx, site, max_depth=0))

    assert ids(items) == [f"https://{HOST}/"]


@pytest.mark.asyncio
async def test_only_hosts_and_ports_of_the_seeds_are_followed(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "https://www.docs.example.com/x", f"https://{HOST}:8443/y", "https://blog.example.com/z", "/ok"))
    site.add("/ok", html("OK"))

    items = await crawl(connector(ctx, site))

    assert ids(items) == [f"https://{HOST}/", f"https://{HOST}/ok"]
    assert all(r.url.host == HOST and r.url.port is None for r in site.requests)


@pytest.mark.asyncio
async def test_path_prefix_limits_followed_links_but_not_seeds(ctx) -> None:
    site = Site()
    site.add("/docs/", html("Docs", "/docs/a", "/blog/post", "/"))
    site.add("/docs/a", html("A"))
    site.add("/blog/post", html("Post"))
    site.add("/", html("Root"))

    items = await crawl(connector(ctx, site, seed_urls=[f"https://{HOST}/docs/"], path_prefix="/docs/"))

    assert ids(items) == [f"https://{HOST}/docs/", f"https://{HOST}/docs/a"]


@pytest.mark.asyncio
async def test_page_cap_stops_the_crawl_and_marks_the_listing_incomplete(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a", "/b", "/c"))
    for name in "abc":
        site.add(f"/{name}", html(name.upper()))

    conn = connector(ctx, site, max_pages=2)
    items = await crawl(conn)

    assert len(items) == 2
    assert conn.stats()["incomplete"] == 1


@pytest.mark.asyncio
async def test_a_crawl_that_finishes_inside_the_cap_is_complete(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a"))
    site.add("/a", html("A"))

    conn = connector(ctx, site, max_pages=2)
    await crawl(conn)

    assert conn.stats()["incomplete"] == 0


@pytest.mark.asyncio
async def test_robots_txt_is_obeyed_and_fetched_once_per_host(ctx) -> None:
    site = Site()
    site.robots("User-agent: *\nDisallow: /private/\n")
    site.add("/", html("Home", "/private/x", "/open"))
    site.add("/private/x", html("Secret"))
    site.add("/open", html("Open"))

    conn = connector(ctx, site)
    items = await crawl(conn)

    assert ids(items) == [f"https://{HOST}/", f"https://{HOST}/open"]
    assert site.fetched("/private/x") == 0
    assert len([r for r in site.requests if r.url.path == "/robots.txt"]) == 1
    assert conn.stats()["skipped"] == 1


@pytest.mark.asyncio
async def test_missing_robots_txt_allows_everything_but_a_broken_one_forbids_everything(ctx) -> None:
    site = Site()
    site.add("/", html("Home"))
    assert ids(await crawl(connector(ctx, site))) == [f"https://{HOST}/"]

    broken = Site()
    broken.robots("oops", status=503)
    broken.add("/", html("Home"))
    with pytest.raises(ConnectorError) as raised:
        await crawl(connector(ctx, broken))
    assert "robots.txt" in raised.value.message
    assert broken.fetched("/") == 0


@pytest.mark.asyncio
async def test_seed_blocked_by_robots_fails_the_listing(ctx) -> None:
    site = Site()
    site.robots("User-agent: *\nDisallow: /\n")
    site.add("/", html("Home"))

    with pytest.raises(ConnectorError) as raised:
        await crawl(connector(ctx, site))

    assert raised.value.code == ConnectorError.LISTING_FAILED


@pytest.mark.asyncio
async def test_crawl_delay_from_robots_is_honoured(ctx) -> None:
    site = Site()
    site.robots("User-agent: *\nCrawl-delay: 2\n")
    site.add("/", html("Home", "/a"))
    site.add("/a", html("A"))
    sleeps: list[float] = []

    async def record(seconds: float) -> None:
        sleeps.append(seconds)

    conn = connector(ctx, site)
    conn._sleep = record
    await crawl(conn)

    assert sleeps and all(0 < delay <= 2 for delay in sleeps)


@pytest.mark.asyncio
async def test_pages_that_say_noindex_or_nofollow_are_honoured(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/hidden", "/stop", "/followed"))
    site.add("/hidden", html("Hidden", head='<meta name="robots" content="noindex">'))
    site.add("/stop", html("Stop", "/behind", head='<meta name="robots" content="nofollow">'))
    site.add("/behind", html("Behind"))
    site.add("/followed", html("Followed", body='<a rel="nofollow" href="/skipped">x</a>'))
    site.add("/skipped", html("Skipped"))

    items = await crawl(connector(ctx, site))

    assert ids(items) == [f"https://{HOST}/", f"https://{HOST}/stop", f"https://{HOST}/followed"]
    assert site.fetched("/behind") == 0 and site.fetched("/skipped") == 0


@pytest.mark.asyncio
async def test_missing_pages_are_absent_and_failing_pages_are_reported_not_dropped(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/gone", "/broken", "/ok"))
    site.add("/gone", "", status=404)
    site.add("/broken", "", status=500)
    site.add("/ok", html("OK"))

    items = await crawl(connector(ctx, site))

    by_id = {item.external_id: item for item in items}
    assert f"https://{HOST}/gone" not in by_id
    assert by_id[f"https://{HOST}/broken"].error == "The server answered 500"
    assert by_id[f"https://{HOST}/ok"].error is None


@pytest.mark.asyncio
async def test_a_failing_seed_fails_the_listing(ctx) -> None:
    site = Site()
    site.add("/", "", status=500)

    with pytest.raises(ConnectorError) as raised:
        await crawl(connector(ctx, site))

    assert raised.value.code == ConnectorError.LISTING_FAILED and "500" in raised.value.message


@pytest.mark.asyncio
async def test_same_host_redirects_are_followed_and_keyed_by_the_final_url(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/old"))
    site.add("/old", "", status=301, headers={"location": "/new"})
    site.add("/new", html("New"))

    items = await crawl(connector(ctx, site))

    assert ids(items) == [f"https://{HOST}/", f"https://{HOST}/new"]


@pytest.mark.asyncio
async def test_redirects_to_another_host_are_not_followed(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/away"))
    site.add("/away", "", status=302, headers={"location": "https://other.com/landing"})
    site.add("/landing", html("Elsewhere"), host="other.com")

    conn = connector(ctx, site)
    items = await crawl(conn)

    assert ids(items) == [f"https://{HOST}/"]
    assert site.paths("other.com") == []
    assert conn.stats()["skipped"] == 1


@pytest.mark.asyncio
async def test_redirect_loops_fail_the_page(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/loop"))
    site.add("/loop", "", status=302, headers={"location": "/loop2"})
    site.add("/loop2", "", status=302, headers={"location": "/loop"})

    items = await crawl(connector(ctx, site))

    assert items[1].error and "redirects too many times" in items[1].error


@pytest.mark.asyncio
async def test_supported_content_types_and_filenames(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/guide", "/notes", "/paper.pdf", "/readme", "/data.zip"))
    site.add("/guide", "# Guide", content_type="text/markdown")
    site.add("/notes", "plain notes", content_type="text/plain; charset=utf-8")
    site.add("/paper.pdf", b"%PDF-1.4", content_type="application/pdf")
    site.add("/readme", "<p>readme</p>", content_type="application/xhtml+xml")
    site.add("/data.zip", b"PK", content_type="application/zip")
    conn = connector(ctx, site)

    items = await crawl(conn)
    fetched = {item.external_id: await conn.fetch_item(item, max_bytes=10_000) for item in items}

    assert [item.external_id.rsplit("/", 1)[-1] for item in items] == ["", "guide", "notes", "paper.pdf", "readme"]
    assert fetched[f"https://{HOST}/guide"].content_type == "text/markdown"
    assert fetched[f"https://{HOST}/guide"].filename == "guide.md"
    assert fetched[f"https://{HOST}/notes"].filename == "notes.txt"
    assert fetched[f"https://{HOST}/paper.pdf"].content_type == "application/pdf"
    assert fetched[f"https://{HOST}/paper.pdf"].filename == "paper.pdf"
    assert fetched[f"https://{HOST}/readme"].content_type == "text/html"
    assert fetched[f"https://{HOST}/readme"].filename == "readme.html"
    assert fetched[f"https://{HOST}/"].filename == "index.html"
    assert fetched[f"https://{HOST}/"].title == "Home"
    assert conn.stats()["skipped"] == 1


@pytest.mark.asyncio
async def test_fetch_item_reuses_the_body_the_crawl_already_read(ctx) -> None:
    site = Site()
    site.add("/", html("Home"))
    conn = connector(ctx, site)
    items = await crawl(conn)

    first = await conn.fetch_item(items[0], max_bytes=10_000)
    assert site.fetched("/") == 1 and b"Home content" in first.content

    again = await conn.fetch_item(items[0], max_bytes=10_000)
    assert site.fetched("/") == 2 and again.content == first.content


@pytest.mark.asyncio
async def test_fetch_item_refuses_a_page_over_the_byte_limit(ctx) -> None:
    site = Site()
    site.add("/", html("Home"))
    conn = connector(ctx, site)
    items = await crawl(conn)

    with pytest.raises(ConnectorError) as raised:
        await conn.fetch_item(items[0], max_bytes=10)

    assert raised.value.code == ConnectorError.ITEM_TOO_LARGE


@pytest.mark.asyncio
async def test_pages_over_the_crawl_size_cap_are_failed_items(ctx, monkeypatch) -> None:
    monkeypatch.setattr(web, "MAX_PAGE_BYTES", 200)
    site = Site()
    site.add("/", html("Home", "/big"))
    site.add("/big", html("Big", body="x" * 500))

    items = await crawl(connector(ctx, site))

    assert items[1].error and "byte limit" in items[1].error


@pytest.mark.asyncio
async def test_unchanged_pages_are_requested_conditionally_and_their_links_still_followed(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a"), headers={"etag": '"home-1"'})
    site.add("/a", html("A"), headers={"etag": '"a-1"', "last-modified": "Wed, 01 Oct 2026 10:00:00 GMT"})
    first = await crawl(connector(ctx, site))
    known = {
        item.external_id: KnownItem(etag=item.etag, modified=item.modified, meta=item.meta) for item in first
    }
    assert first[0].etag == '"home-1"' and first[1].modified == "Wed, 01 Oct 2026 10:00:00 GMT"
    site.requests.clear()

    conn = connector(ctx, site)
    second = await crawl(conn, known)

    assert ids(second) == ids(first)
    home_request = [r for r in site.requests if r.url.path == "/"][0]
    a_request = [r for r in site.requests if r.url.path == "/a"][0]
    assert home_request.headers["if-none-match"] == '"home-1"'
    assert a_request.headers["if-none-match"] == '"a-1"'
    assert a_request.headers["if-modified-since"] == "Wed, 01 Oct 2026 10:00:00 GMT"
    assert second[0].etag == '"home-1"' and second[0].meta["links"] == [f"https://{HOST}/a"]
    assert second[0].name == "Home"


@pytest.mark.asyncio
async def test_a_changed_page_is_downloaded_again(ctx) -> None:
    site = Site()
    site.add("/", html("Home v1"), headers={"etag": '"v1"'})
    first = await crawl(connector(ctx, site))
    known = {item.external_id: KnownItem(item.etag, item.modified, item.meta) for item in first}
    site.add("/", html("Home v2"), headers={"etag": '"v2"'})

    conn = connector(ctx, site)
    second = await crawl(conn, known)

    assert second[0].etag == '"v2"' and second[0].size
    fetched = await conn.fetch_item(second[0], max_bytes=10_000)
    assert b"Home v2" in fetched.content


@pytest.mark.asyncio
async def test_the_crawl_sends_no_credentials_and_keeps_no_cookies(ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a"), headers={"set-cookie": "session=abc; Path=/"})
    site.add("/a", html("A"))

    await crawl(connector(ctx, site))

    assert site.requests
    for request in site.requests:
        assert "cookie" not in request.headers
        assert "authorization" not in request.headers
        assert request.headers["user-agent"].startswith("SOITKnowledgeBot/")


# ------------------------------------------------------------------ egress


@pytest.mark.asyncio
async def test_private_addresses_are_refused_with_an_actionable_error(ctx) -> None:
    site = Site()
    site.add("/", html("Home"))
    guard = GovernedEgressGuard(address_resolver=PublicResolver("10.0.0.7"))
    conn = web.WebConnector(
        ctx,
        web.validate_config({"seed_urls": [f"https://{HOST}/"]}),
        client_factory=lambda: web.build_client(ctx, egress_guard=guard, transport=httpx.MockTransport(site)),
    )

    with pytest.raises(ConnectorError) as raised:
        await crawl(conn)

    assert raised.value.code == ConnectorError.EGRESS_BLOCKED
    assert "EGRESS_PRIVATE_NETWORKS" in raised.value.message
    assert site.requests == []

    report = await conn.test_connection()
    assert report.ok is False and "egress policy" in report.message


@pytest.mark.asyncio
async def test_hosts_outside_the_allowlist_are_refused(ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "egress_allowlist", ["unrelated.test"])
    monkeypatch.setattr(egress, "_egress_policy", None)
    site = Site()
    site.add("/", html("Home"))

    with pytest.raises(ConnectorError) as raised:
        await crawl(connector(ctx, site))

    assert raised.value.code == ConnectorError.EGRESS_BLOCKED and site.requests == []


@pytest.mark.asyncio
async def test_network_failure_on_a_page_is_a_failed_item_and_on_the_seed_a_failed_listing(ctx) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/":
            return httpx.Response(200, headers={"content-type": "text/html"}, content=html("Home", "/slow").encode())
        raise httpx.ReadTimeout("slow", request=request)

    guard = GovernedEgressGuard(address_resolver=PublicResolver())
    conn = web.WebConnector(
        ctx,
        web.validate_config({"seed_urls": [f"https://{HOST}/"]}),
        client_factory=lambda: web.build_client(ctx, egress_guard=guard, transport=httpx.MockTransport(broken)),
    )

    items = await crawl(conn)

    assert items[1].error and "timed out" in items[1].error


# ------------------------------------------------------- test connection


@pytest.mark.asyncio
async def test_test_connection_samples_pages_within_the_limit(ctx) -> None:
    site = Site()
    site.add("/", html("Home", *[f"/p{i}" for i in range(10)]))
    for i in range(10):
        site.add(f"/p{i}", html(f"P{i}"))

    report = await connector(ctx, site).test_connection(sample_size=3)

    assert report.ok is True and len(report.sample) == 3
    assert "Read 3 pages" in report.message
    assert len(site.paths()) == 3


@pytest.mark.asyncio
async def test_test_connection_reports_an_unreachable_seed(ctx) -> None:
    site = Site()
    site.add("/", "", status=500)

    report = await connector(ctx, site).test_connection()

    assert report.ok is False and "500" in report.message


def test_registration_describes_the_connector(ctx) -> None:
    registration = web.REGISTRATION

    assert registration.descriptor.kind == "web" and registration.descriptor.secret == "none"
    assert {field.key for field in registration.descriptor.fields} == {"seed_urls", "path_prefix", "max_depth", "max_pages"}
    built = registration.factory(ctx, {"seed_urls": ["https://example.com/"]}, None)
    assert isinstance(built, web.WebConnector)
