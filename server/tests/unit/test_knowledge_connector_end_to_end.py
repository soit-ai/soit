"""The sync engine driving the real connectors over faked network transports."""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import select

from app.adapters.connectors import s3, web
from app.adapters.connectors.common import RESOURCE_S3, make_client
from app.kernel.ports.connectors import ConnectorRegistration, ConnectorRegistry
from app.kernel.security import egress
from app.kernel.security.egress import GovernedEgressGuard
from app.modules.knowledge.application.connector_sync import (
    KnowledgeSyncEngine,
    create_sync_run,
)
from app.modules.knowledge.application.runtime_schemas import KnowledgeCreate
from app.modules.knowledge.domain.models import (
    KnowledgeDocument,
    KnowledgeSource,
    KnowledgeSourceItem,
)
from app.settings.settings import settings
from tests.unit.test_knowledge_runtime_service import build_knowledge_test_service
from tests.unit.test_s3_connector import (
    NOW,
    SECRET_JSON,
    FakeS3,
    PublicResolver,
    contents,
    listing,
)
from tests.unit.test_web_connector import HOST, Site, html


@pytest.fixture(autouse=True)
def egress_policy(monkeypatch):
    monkeypatch.setattr(settings, "enable_egress_policy", True)
    monkeypatch.setattr(settings, "egress_allowlist", ["*.amazonaws.com", "s3.amazonaws.com", "*.example.com"])
    monkeypatch.setattr(settings, "egress_blocklist", [])
    monkeypatch.setattr(settings, "egress_private_networks", [])
    monkeypatch.setattr(egress, "_egress_policy", None)


class _Secrets:
    async def get_secret(self, secret_id, **kwargs):
        return SECRET_JSON


async def _engine(async_db, ctx, registration: ConnectorRegistration, *, kind: str, config: dict, **source_kwargs):
    service, _storage, _vector = build_knowledge_test_service(async_db, ctx)
    knowledge = await service.create_knowledge(
        KnowledgeCreate(name="kb_e2e", type="document", default_embedding_model_ref="model:test:embedding")
    )
    source = KnowledgeSource(
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        knowledge_id=knowledge.id,
        name="source",
        connector_kind=kind,
        config_json=config,
        created_by=ctx.user_id,
        **source_kwargs,
    )
    async_db.add(source)
    await async_db.commit()
    registry = ConnectorRegistry()
    registry.register(registration)
    engine = KnowledgeSyncEngine(
        db=async_db, ctx=ctx, runtime=service, registry=registry, secrets_port=_Secrets()  # type: ignore[arg-type]
    )
    return knowledge, source, engine


async def _run(async_db, engine, source):
    run = await create_sync_run(async_db, source, trigger="manual", requested_by="u")
    return await engine.execute(run)


async def _live_docs(async_db, knowledge_id):
    rows = (
        await async_db.exec(
            select(KnowledgeDocument).where(
                KnowledgeDocument.knowledge_id == knowledge_id,
                KnowledgeDocument.deleted_at.is_(None),
                KnowledgeDocument.is_latest.is_(True),
            )
        )
    ).scalars().all()
    return sorted(rows, key=lambda doc: doc.external_id or "")


def _s3_registration(ctx, fake: FakeS3) -> ConnectorRegistration:
    guard = GovernedEgressGuard(address_resolver=PublicResolver())

    def factory(_ctx, config, secret_value):
        return s3.S3Connector(
            ctx,
            s3.validate_config(config),
            s3.parse_credentials(secret_value),
            client_factory=lambda: make_client(ctx, RESOURCE_S3, egress_guard=guard, transport=httpx.MockTransport(fake)),
            clock=lambda: NOW,
        )

    return ConnectorRegistration(
        descriptor=s3.DESCRIPTOR,
        validate_config=s3.validate_config,
        validate_credentials=s3.validate_credentials,
        factory=factory,
    )


def _web_registration(ctx, site: Site) -> ConnectorRegistration:
    guard = GovernedEgressGuard(address_resolver=PublicResolver())

    def factory(_ctx, config, _secret_value):
        return web.WebConnector(
            ctx,
            web.validate_config(config),
            client_factory=lambda: web.build_client(ctx, egress_guard=guard, transport=httpx.MockTransport(site)),
        )

    return ConnectorRegistration(
        descriptor=web.DESCRIPTOR,
        validate_config=web.validate_config,
        validate_credentials=web.validate_credentials,
        factory=factory,
    )


@pytest.mark.asyncio
async def test_s3_bucket_syncs_end_to_end(async_db, ctx) -> None:
    fake = FakeS3()
    fake.objects = {"handbook/a.md": b"# A", "handbook/b.txt": b"bee", "handbook/skip.png": b"png"}
    fake.pages = [
        listing(contents("handbook/a.md", etag="a1", size=3), contents("handbook/b.txt", etag="b1", size=3), contents("handbook/skip.png"))
    ] * 5
    knowledge, source, engine = await _engine(
        async_db,
        ctx,
        _s3_registration(ctx, fake),
        kind="s3",
        config={"bucket": "docs", "prefix": "handbook/"},
        secret_id="sec_s3key",
        delete_removed=True,
    )

    run = await _run(async_db, engine, source)

    assert (run.status, run.added_count, run.skipped_count) == ("succeeded", 2, 1)
    docs = await _live_docs(async_db, knowledge.id)
    assert [(doc.external_id, doc.mime_type, doc.source_uri) for doc in docs] == [
        ("handbook/a.md", "text/markdown", "s3://docs/handbook/a.md"),
        ("handbook/b.txt", "text/plain", "s3://docs/handbook/b.txt"),
    ]

    fake.requests.clear()
    fake.pages = [
        listing(contents("handbook/a.md", etag="a1", size=3), contents("handbook/b.txt", etag="b1", size=3))
    ] * 5
    run = await _run(async_db, engine, source)
    assert (run.added_count, run.unchanged_count) == (0, 2)
    assert [r for r in fake.requests if "list-type" not in r.url.query.decode()] == []

    fake.pages = [listing(contents("handbook/a.md", etag="a2", size=8))] * 5
    fake.objects["handbook/a.md"] = b"# A, v2!"
    run = await _run(async_db, engine, source)
    assert (run.updated_count, run.removed_count) == (1, 1)
    assert [doc.external_id for doc in await _live_docs(async_db, knowledge.id)] == ["handbook/a.md"]
    assert "very-secret-key-value" not in repr([doc.model_dump() for doc in await _live_docs(async_db, knowledge.id)])


@pytest.mark.asyncio
async def test_web_crawl_syncs_end_to_end_with_conditional_requests(async_db, ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a", "/b"), headers={"etag": '"home"'})
    site.add("/a", html("A page"), headers={"etag": '"a1"'})
    site.add("/b", html("B page"), headers={"etag": '"b1"'})
    knowledge, source, engine = await _engine(
        async_db,
        ctx,
        _web_registration(ctx, site),
        kind="web",
        config={"seed_urls": [f"https://{HOST}/"]},
        delete_removed=True,
    )

    run = await _run(async_db, engine, source)
    assert (run.status, run.added_count) == ("succeeded", 3)
    docs = await _live_docs(async_db, knowledge.id)
    assert {doc.title for doc in docs} == {"Home", "A page", "B page"}
    assert {doc.mime_type for doc in docs} == {"text/html"}
    items = {item.external_id: item for item in (await async_db.exec(select(KnowledgeSourceItem))).scalars().all()}
    assert items[f"https://{HOST}/"].meta_json["links"] == [f"https://{HOST}/a", f"https://{HOST}/b"]

    site.requests.clear()
    run = await _run(async_db, engine, source)
    assert (run.added_count, run.updated_count, run.unchanged_count) == (0, 0, 3)
    assert all(r.headers.get("if-none-match") for r in site.requests if r.url.path != "/robots.txt")

    site.add("/a", html("A page, edited"), headers={"etag": '"a2"'})
    site.add("/b", "", status=404)
    run = await _run(async_db, engine, source)
    assert (run.updated_count, run.removed_count, run.unchanged_count) == (1, 1, 1)
    assert {doc.title for doc in await _live_docs(async_db, knowledge.id)} == {"Home", "A page, edited"}


@pytest.mark.asyncio
async def test_web_crawl_hitting_its_page_cap_never_deletes(async_db, ctx) -> None:
    site = Site()
    site.add("/", html("Home", "/a", "/b"))
    site.add("/a", html("A"))
    site.add("/b", html("B"))
    knowledge, source, engine = await _engine(
        async_db,
        ctx,
        _web_registration(ctx, site),
        kind="web",
        config={"seed_urls": [f"https://{HOST}/"]},
        delete_removed=True,
    )
    await _run(async_db, engine, source)
    source.config_json = {"seed_urls": [f"https://{HOST}/"], "max_pages": 2}
    await async_db.commit()

    run = await _run(async_db, engine, source)

    assert run.truncated is True and run.removed_count == 0
    assert len(await _live_docs(async_db, knowledge.id)) == 3


@pytest.mark.asyncio
async def test_a_web_source_with_a_missing_seed_fails_without_removing_anything(async_db, ctx) -> None:
    site = Site()
    site.add("/", html("Home"))
    knowledge, source, engine = await _engine(
        async_db,
        ctx,
        _web_registration(ctx, site),
        kind="web",
        config={"seed_urls": [f"https://{HOST}/"]},
        delete_removed=True,
    )
    await _run(async_db, engine, source)
    site.add("/", "", status=404)

    run = await _run(async_db, engine, source)

    assert run.status == "failed" and "not found" in run.error_message
    assert len(await _live_docs(async_db, knowledge.id)) == 1
