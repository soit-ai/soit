"""Entrypoint tests for the knowledge source API."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest
from fastapi import status
from sqlalchemy import select

from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.main import app
from app.middleware.auth import get_current_context
from app.modules.knowledge.application.connector_sync import KnowledgeSyncEngine
from app.modules.knowledge.domain.models import (
    KnowledgeIndex,
    KnowledgeSource,
    KnowledgeSyncRun,
)
from app.settings.settings import settings
from app.wiring import connectors as wiring_connectors
from tests.unit.knowledge_connector_support import (
    FakeRemote,
    FakeSecretsPort,
    build_registry,
)
from tests.unit.test_knowledge_runtime_service import build_knowledge_test_service

pytestmark = [pytest.mark.asyncio, pytest.mark.usefixtures("remote")]

S3_SECRET = json.dumps({"access_key_id": "AKIAEXAMPLEKEYID", "secret_access_key": "super-secret-access-key-value"})


@pytest.fixture
def remote(monkeypatch) -> FakeRemote:
    """The real connector kinds plus a fake one that talks to an in-memory remote."""
    fake_remote = FakeRemote()
    registry = wiring_connectors.build_connector_registry()
    registry.register(build_registry(fake_remote).get("fake"))
    monkeypatch.setattr(wiring_connectors, "get_connector_registry", lambda: registry)
    return fake_remote


def _act_as(ctx: RequestContext, user_id: str, role: str) -> RequestContext:
    member = replace(ctx, user_id=user_id, workspace_role=role, tenant_role="Member")

    async def _override() -> RequestContext:
        return member

    app.dependency_overrides[get_current_context] = _override
    return member


async def _knowledge(async_client, async_db, ctx, *, name: str = "kb-sources", visibility: str | None = None, with_index: bool = True) -> str:
    payload: dict[str, object] = {"name": name, "knowledge_type": "document"}
    if visibility:
        payload["visibility"] = visibility
    response = await async_client.post("/api/v1/knowledge", json=payload)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    knowledge_id = response.json()["data"]["id"]
    if with_index:
        async_db.add(
            KnowledgeIndex(
                tenant_id=ctx.tenant_id,
                workspace_id=ctx.workspace_id,
                knowledge_id=knowledge_id,
                name="primary",
                is_primary=True,
                provider="milvus",
                embedding_model_ref="model:test:embedding",
                dimension=3,
                metric_type="cosine",
                status="ready",
            )
        )
        await async_db.commit()
    return knowledge_id


def _web_payload(**overrides) -> dict:
    payload: dict = {
        "name": "docs site",
        "connector_kind": "web",
        "config": {"seed_urls": ["https://docs.example.com/"], "max_depth": 1},
    }
    payload.update(overrides)
    return payload


async def _create(async_client, knowledge_id: str, **overrides) -> dict:
    response = await async_client.post(f"/api/v1/knowledge/{knowledge_id}/sources", json=_web_payload(**overrides))
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]


async def _secret(async_client, value: str = S3_SECRET) -> str:
    response = await async_client.post("/api/v1/secrets", json={"name": f"s3-{utc_now().timestamp()}", "value": value})
    assert response.status_code == status.HTTP_201_CREATED, response.text
    return response.json()["data"]["id"]


def _base(knowledge_id: str) -> str:
    return f"/api/v1/knowledge/{knowledge_id}/sources"


# ------------------------------------------------------------- connectors


async def test_connector_catalog_describes_each_kind_and_its_settings(async_client) -> None:
    response = await async_client.get("/api/v1/knowledge/connectors")

    assert response.status_code == status.HTTP_200_OK
    catalog = {item["kind"]: item for item in response.json()["data"]}
    assert {"s3", "web", "fake"} <= set(catalog)
    s3 = catalog["s3"]
    assert s3["secret"] == "required" and s3["secret_help"]
    fields = {field["key"]: field for field in s3["fields"]}
    assert fields["bucket"]["required"] is True and fields["include"]["type"] == "string_list"
    assert fields["region"]["default"] == "us-east-1"
    assert {field["key"] for field in catalog["web"]["fields"]} == {"seed_urls", "path_prefix", "max_depth", "max_pages"}
    assert catalog["web"]["secret"] == "none"


# ---------------------------------------------------------------- create


async def test_create_source_returns_the_source_with_defaults_and_writes_an_audit_event(
    async_client, async_db, ctx
) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)

    source = await _create(async_client, knowledge_id, schedule_cron="0 3 * * *", schedule_timezone="Asia/Shanghai")

    assert source["id"].startswith("ksrc_")
    assert source["knowledge_id"] == knowledge_id and source["tenant_id"] == ctx.tenant_id
    assert source["connector_kind"] == "web" and source["enabled"] is True and source["delete_removed"] is False
    assert source["config"]["seed_urls"] == ["https://docs.example.com/"]
    assert source["limits"] == {"max_items": 1000, "max_item_bytes": 5 * 1024 * 1024, "max_total_bytes": 256 * 1024 * 1024}
    assert source["next_sync_at"] is not None and source["last_status"] is None and source["active_run_id"] is None
    events = (await async_db.exec(select(AuditEvent).where(AuditEvent.resource_id == source["id"]))).scalars().all()
    assert [(e.event_type, e.actor_user_id, e.tenant_id) for e in events] == [
        ("knowledge.source.created", ctx.user_id, ctx.tenant_id)
    ]


async def test_create_without_a_schedule_means_manual_sync_only(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)

    source = await _create(async_client, knowledge_id)

    assert source["schedule_cron"] is None and source["next_sync_at"] is None


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"connector_kind": "ftp"}, "Unknown connector kind"),
        ({"config": {}}, "at least one URL"),
        ({"config": {"seed_urls": ["https://a.example.com/"], "token": "x"}}, "looks like a credential"),
        ({"config": {"seed_urls": ["https://a.example.com/"], "max_depth": 9}}, "between 0 and 5"),
        ({"schedule_cron": "not a cron"}, "Invalid schedule"),
        ({"schedule_cron": "* * * * *"}, "at most once every"),
        ({"schedule_cron": "0 3 * * *", "schedule_timezone": "Mars/Base"}, "Unknown time zone"),
        ({"secret_id": "sec_whatever"}, "does not take a secret"),
        ({"limits": {"max_items": 10**9}}, "max_items may be at most"),
        ({"name": ""}, None),
    ],
)
async def test_invalid_sources_are_rejected_with_a_reason(async_client, async_db, ctx, overrides, message) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)

    response = await async_client.post(_base(knowledge_id), json=_web_payload(**overrides))

    assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY), response.text
    if message:
        assert message in json.dumps(response.json())


async def test_inline_credentials_are_never_accepted_or_echoed(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)

    response = await async_client.post(
        _base(knowledge_id),
        json={
            "name": "bucket",
            "connector_kind": "s3",
            "config": {"bucket": "docs", "secret_access_key": "inline-secret-value", "access_key_id": "AKIAINLINE"},
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "looks like a credential" in response.text
    assert "inline-secret-value" not in response.text and "AKIAINLINE" not in response.text
    assert (await async_db.exec(select(KnowledgeSource))).scalars().all() == []


async def test_names_are_unique_per_knowledge_base_and_sources_are_capped(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    await _create(async_client, knowledge_id, name="Docs")

    duplicate = await async_client.post(_base(knowledge_id), json=_web_payload(name="docs"))
    assert duplicate.status_code == status.HTTP_409_CONFLICT

    for index in range(19):
        await _create(async_client, knowledge_id, name=f"extra {index}")
    over = await async_client.post(_base(knowledge_id), json=_web_payload(name="one too many"))
    assert over.status_code == status.HTTP_400_BAD_REQUEST and "at most 20" in over.text


async def test_s3_source_needs_a_secret_that_exists_and_has_the_right_shape(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    payload = {"name": "bucket", "connector_kind": "s3", "config": {"bucket": "docs"}}

    missing = await async_client.post(_base(knowledge_id), json=payload)
    assert missing.status_code == status.HTTP_400_BAD_REQUEST and "needs a secret" in missing.text

    unknown = await async_client.post(_base(knowledge_id), json={**payload, "secret_id": "sec_doesnotexist"})
    assert unknown.status_code == status.HTTP_400_BAD_REQUEST and "not found" in unknown.text

    wrong_shape = await _secret(async_client, "hunter2 is not json")
    bad = await async_client.post(_base(knowledge_id), json={**payload, "secret_id": wrong_shape})
    assert bad.status_code == status.HTTP_400_BAD_REQUEST and "must be JSON" in bad.text
    assert "hunter2" not in bad.text

    good_secret = await _secret(async_client)
    created = await async_client.post(_base(knowledge_id), json={**payload, "secret_id": good_secret})
    assert created.status_code == status.HTTP_201_CREATED, created.text
    body = created.json()["data"]
    assert body["secret_id"] == good_secret


async def test_secret_values_never_appear_in_responses_storage_or_audit(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    secret_id = await _secret(async_client)
    created = await async_client.post(
        _base(knowledge_id),
        json={"name": "bucket", "connector_kind": "s3", "config": {"bucket": "docs"}, "secret_id": secret_id},
    )
    source_id = created.json()["data"]["id"]

    responses = [
        created.text,
        (await async_client.get(_base(knowledge_id))).text,
        (await async_client.get(f"{_base(knowledge_id)}/{source_id}")).text,
        (await async_client.post(f"{_base(knowledge_id)}/{source_id}/test")).text,
        (await async_client.patch(f"{_base(knowledge_id)}/{source_id}", json={"name": "renamed"})).text,
    ]

    for text in responses:
        assert "super-secret-access-key-value" not in text and "AKIAEXAMPLEKEYID" not in text
    stored = (await async_db.exec(select(KnowledgeSource))).scalars().one()
    assert "super-secret" not in json.dumps(stored.config_json) and "AKIAEXAMPLEKEYID" not in json.dumps(stored.config_json)
    audit = (await async_db.exec(select(AuditEvent).where(AuditEvent.resource_id == source_id))).scalars().all()
    assert audit and all("super-secret" not in json.dumps(event.payload_json) for event in audit)


# ----------------------------------------------------------- read / update


async def test_list_and_get_show_the_sources_of_one_knowledge_base_only(async_client, async_db, ctx) -> None:
    first = await _knowledge(async_client, async_db, ctx, name="kb-one")
    second = await _knowledge(async_client, async_db, ctx, name="kb-two")
    a = await _create(async_client, first, name="a")
    await _create(async_client, second, name="b")

    listed = (await async_client.get(_base(first))).json()["data"]
    got = await async_client.get(f"{_base(first)}/{a['id']}")
    wrong_kb = await async_client.get(f"{_base(second)}/{a['id']}")

    assert [item["name"] for item in listed] == ["a"]
    assert got.status_code == 200 and got.json()["data"]["id"] == a["id"]
    assert wrong_kb.status_code == 404


async def test_update_changes_only_the_fields_sent_and_recomputes_the_schedule(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id, schedule_cron="0 3 * * *")
    url = f"{_base(knowledge_id)}/{source['id']}"

    renamed = await async_client.patch(url, json={"name": "Docs v2", "delete_removed": True})
    assert renamed.status_code == 200
    body = renamed.json()["data"]
    assert body["name"] == "Docs v2" and body["delete_removed"] is True
    assert body["schedule_cron"] == "0 3 * * *" and body["next_sync_at"] == source["next_sync_at"]

    paused = (await async_client.patch(url, json={"enabled": False})).json()["data"]
    assert paused["enabled"] is False and paused["next_sync_at"] is None

    resumed = (await async_client.patch(url, json={"enabled": True, "schedule_cron": "30 4 * * *"})).json()["data"]
    assert resumed["next_sync_at"] is not None and resumed["schedule_cron"] == "30 4 * * *"

    cleared = (await async_client.patch(url, json={"schedule_cron": None})).json()["data"]
    assert cleared["schedule_cron"] is None and cleared["next_sync_at"] is None

    reconfigured = await async_client.patch(url, json={"config": {"seed_urls": ["https://other.example.com/"]}})
    assert reconfigured.json()["data"]["config"]["seed_urls"] == ["https://other.example.com/"]
    bad = await async_client.patch(url, json={"config": {"seed_urls": []}})
    assert bad.status_code == 400

    events = (
        await async_db.exec(
            select(AuditEvent).where(AuditEvent.resource_id == source["id"], AuditEvent.event_type == "knowledge.source.updated")
        )
    ).scalars().all()
    assert events and "name" in events[0].payload_json["changed"]


async def test_limit_changes_merge_into_the_stored_caps(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id, limits={"max_items": 40, "max_item_bytes": 2048})
    url = f"{_base(knowledge_id)}/{source['id']}"

    added = (await async_client.patch(url, json={"limits": {"max_total_bytes": 4096}})).json()["data"]
    assert added["limits"] == {"max_items": 40, "max_item_bytes": 2048, "max_total_bytes": 4096}

    reset_one = (await async_client.patch(url, json={"limits": {"max_items": None}})).json()["data"]
    assert reset_one["limits"]["max_items"] == 1000
    assert reset_one["limits"]["max_item_bytes"] == 2048

    reset_all = (await async_client.patch(url, json={"limits": None})).json()["data"]
    assert reset_all["limits"] == {"max_items": 1000, "max_item_bytes": 5 * 1024 * 1024, "max_total_bytes": 256 * 1024 * 1024}


async def test_removing_the_secret_from_an_s3_source_is_refused(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    secret_id = await _secret(async_client)
    created = await async_client.post(
        _base(knowledge_id),
        json={"name": "bucket", "connector_kind": "s3", "config": {"bucket": "docs"}, "secret_id": secret_id},
    )
    source_id = created.json()["data"]["id"]

    response = await async_client.patch(f"{_base(knowledge_id)}/{source_id}", json={"secret_id": None})

    assert response.status_code == status.HTTP_400_BAD_REQUEST and "needs a secret" in response.text


async def test_delete_removes_the_source_and_cancels_its_queued_run(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id)
    url = f"{_base(knowledge_id)}/{source['id']}"
    queued = (await async_client.post(f"{url}/sync")).json()["data"]

    deleted = await async_client.delete(url)

    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert (await async_client.get(url)).status_code == 404
    assert (await async_client.get(_base(knowledge_id))).json()["data"] == []
    run = (await async_db.exec(select(KnowledgeSyncRun).where(KnowledgeSyncRun.id == queued["id"]))).scalars().one()
    await async_db.refresh(run)
    assert run.status == "canceled"
    events = (await async_db.exec(select(AuditEvent).where(AuditEvent.resource_id == source["id"]))).scalars().all()
    assert "knowledge.source.deleted" in {event.event_type for event in events}


# ---------------------------------------------------------- test connection


async def test_a_saved_source_can_be_tested_and_returns_a_sample(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id, connector_kind="fake", config={"bucket": "docs"})

    response = await async_client.post(f"{_base(knowledge_id)}/{source['id']}/test")

    assert response.status_code == 200
    assert response.json()["data"] == {"ok": True, "message": "ok", "sample": []}


async def test_an_unsaved_connection_can_be_tested_and_failures_come_back_as_a_report(
    async_client, async_db, ctx
) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)

    ok = await async_client.post(f"{_base(knowledge_id)}/test", json={"connector_kind": "fake", "config": {"bucket": "x"}})
    bad_config = await async_client.post(f"{_base(knowledge_id)}/test", json={"connector_kind": "web", "config": {}})

    assert ok.json()["data"]["ok"] is True
    assert bad_config.status_code == 200
    assert bad_config.json()["data"]["ok"] is False and "at least one URL" in bad_config.json()["data"]["message"]


async def test_testing_a_private_address_reports_the_egress_refusal(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)

    response = await async_client.post(
        f"{_base(knowledge_id)}/test",
        json={"connector_kind": "web", "config": {"seed_urls": ["http://127.0.0.1:8080/"]}},
    )

    report = response.json()["data"]
    assert response.status_code == 200 and report["ok"] is False
    assert "egress policy" in report["message"]


# --------------------------------------------------------------------- sync


async def test_sync_queues_a_run_and_a_second_one_is_a_conflict(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id)
    url = f"{_base(knowledge_id)}/{source['id']}"

    first = await async_client.post(f"{url}/sync")
    second = await async_client.post(f"{url}/sync")

    assert first.status_code == status.HTTP_202_ACCEPTED
    run = first.json()["data"]
    assert run["status"] == "queued" and run["trigger"] == "manual" and run["source_id"] == source["id"]
    assert run["requested_by"] == ctx.user_id
    assert second.status_code == status.HTTP_409_CONFLICT
    detail = (await async_client.get(url)).json()["data"]
    assert detail["active_run_id"] == run["id"] and detail["last_status"] == "queued"


async def test_sync_is_refused_for_a_disabled_source_and_a_knowledge_base_without_an_index(
    async_client, async_db, ctx
) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id, enabled=False)
    disabled = await async_client.post(f"{_base(knowledge_id)}/{source['id']}/sync")
    assert disabled.status_code == status.HTTP_400_BAD_REQUEST and "disabled" in disabled.text

    bare = await _knowledge(async_client, async_db, ctx, name="kb-bare", with_index=False)
    bare_source = await _create(async_client, bare)
    no_index = await async_client.post(f"{_base(bare)}/{bare_source['id']}/sync")
    assert no_index.status_code == status.HTTP_400_BAD_REQUEST and "no index" in no_index.text


async def test_queued_run_can_be_canceled_and_the_source_synced_again(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id)
    url = f"{_base(knowledge_id)}/{source['id']}"
    run = (await async_client.post(f"{url}/sync")).json()["data"]

    canceled = await async_client.post(f"{url}/runs/{run['id']}/cancel")

    assert canceled.status_code == 200 and canceled.json()["data"]["status"] == "canceled"
    again_cancel = await async_client.post(f"{url}/runs/{run['id']}/cancel")
    assert again_cancel.status_code == status.HTTP_409_CONFLICT
    assert (await async_client.post(f"{url}/sync")).status_code == status.HTTP_202_ACCEPTED
    assert (await async_client.get(url)).json()["data"]["last_status"] == "queued"


async def test_cancel_of_a_running_run_is_a_request_the_worker_honours(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id)
    url = f"{_base(knowledge_id)}/{source['id']}"
    run = (await async_client.post(f"{url}/sync")).json()["data"]
    row = (await async_db.exec(select(KnowledgeSyncRun).where(KnowledgeSyncRun.id == run["id"]))).scalars().one()
    row.status = "running"
    await async_db.commit()

    response = await async_client.post(f"{url}/runs/{run['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "running" and response.json()["data"]["cancel_requested"] is True


async def test_run_history_and_detail_show_counts_and_per_item_outcomes(async_client, async_db, ctx, remote) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id, connector_kind="fake", config={"bucket": "docs"})
    url = f"{_base(knowledge_id)}/{source['id']}"
    remote.put("good.txt", b"fine")
    remote.put("bad.txt", b"x", fail_fetch="access denied")
    queued = (await async_client.post(f"{url}/sync")).json()["data"]

    runtime, _storage, _vector = build_knowledge_test_service(async_db, ctx)
    engine = KnowledgeSyncEngine(
        db=async_db, ctx=ctx, runtime=runtime, registry=wiring_connectors.get_connector_registry(), secrets_port=FakeSecretsPort()
    )
    row = (await async_db.exec(select(KnowledgeSyncRun).where(KnowledgeSyncRun.id == queued["id"]))).scalars().one()
    await engine.execute(row)

    history = (await async_client.get(f"{url}/runs")).json()["data"]
    detail = (await async_client.get(f"{url}/runs/{queued['id']}")).json()["data"]
    source_now = (await async_client.get(url)).json()["data"]

    assert [item["id"] for item in history] == [queued["id"]]
    assert history[0]["status"] == "partial" and history[0]["added_count"] == 1 and history[0]["failed_count"] == 1
    assert {(o["external_id"], o["outcome"]) for o in detail["outcomes"]} == {("good.txt", "added"), ("bad.txt", "failed")}
    assert next(o for o in detail["outcomes"] if o["outcome"] == "failed")["error"] == "access denied"
    assert source_now["last_status"] == "partial" and source_now["last_counts"]["added"] == 1
    assert source_now["active_run_id"] is None
    assert "outcomes" not in history[0]


async def test_run_history_is_paged_newest_first(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id)
    url = f"{_base(knowledge_id)}/{source['id']}"
    ids = []
    for _ in range(3):
        run = (await async_client.post(f"{url}/sync")).json()["data"]
        ids.append(run["id"])
        await async_client.post(f"{url}/runs/{run['id']}/cancel")

    page = (await async_client.get(f"{url}/runs", params={"limit": 2})).json()["data"]
    rest = (await async_client.get(f"{url}/runs", params={"limit": 2, "offset": 2})).json()["data"]

    assert [item["id"] for item in page + rest] == list(reversed(ids))
    assert (await async_client.get(f"{url}/runs/ksync_unknown")).status_code == 404


# -------------------------------------------------------- isolation and RBAC


async def test_another_tenant_cannot_see_or_touch_sources(async_client, async_db, ctx, tenant2_ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id)
    url = f"{_base(knowledge_id)}/{source['id']}"
    run = (await async_client.post(f"{url}/sync")).json()["data"]

    _act_as(tenant2_ctx, "outsider", "Owner")

    for method, path, body in (
        ("GET", _base(knowledge_id), None),
        ("GET", url, None),
        ("PATCH", url, {"name": "hijack"}),
        ("DELETE", url, None),
        ("POST", f"{url}/test", None),
        ("POST", f"{url}/sync", None),
        ("GET", f"{url}/runs", None),
        ("GET", f"{url}/runs/{run['id']}", None),
        ("POST", f"{url}/runs/{run['id']}/cancel", None),
        ("POST", _base(knowledge_id), _web_payload(name="intruder")),
    ):
        response = await async_client.request(method, path, json=body)
        assert response.status_code == 404, (method, path, response.status_code, response.text)

    stored = (await async_db.exec(select(KnowledgeSource))).scalars().all()
    assert [(row.name, row.deleted_at) for row in stored] == [("docs site", None)]


async def test_viewers_can_read_sources_but_not_change_or_run_them(async_client, async_db, ctx) -> None:
    knowledge_id = await _knowledge(async_client, async_db, ctx)
    source = await _create(async_client, knowledge_id)
    url = f"{_base(knowledge_id)}/{source['id']}"
    run = (await async_client.post(f"{url}/sync")).json()["data"]

    _act_as(ctx, "viewer-vic", "Viewer")

    assert (await async_client.get(_base(knowledge_id))).status_code == 200
    assert (await async_client.get(url)).status_code == 200
    assert (await async_client.get(f"{url}/runs")).status_code == 200
    assert (await async_client.get(f"{url}/runs/{run['id']}")).status_code == 200
    assert (await async_client.get("/api/v1/knowledge/connectors")).status_code == 200
    for method, path, body in (
        ("POST", _base(knowledge_id), _web_payload(name="viewer made")),
        ("POST", f"{_base(knowledge_id)}/test", {"connector_kind": "fake", "config": {"bucket": "x"}}),
        ("PATCH", url, {"name": "nope"}),
        ("DELETE", url, None),
        ("POST", f"{url}/test", None),
        ("POST", f"{url}/sync", None),
        ("POST", f"{url}/runs/{run['id']}/cancel", None),
    ):
        response = await async_client.request(method, path, json=body)
        assert response.status_code == 403, (method, path, response.status_code)


async def test_private_knowledge_keeps_its_sources_from_other_members(async_client, async_db, ctx) -> None:
    _act_as(ctx, "dev-alice", "Dev")
    knowledge_id = await _knowledge(async_client, async_db, ctx, name="kb-private", visibility="private")
    source = await _create(async_client, knowledge_id)

    _act_as(ctx, "dev-bob", "Dev")
    url = f"{_base(knowledge_id)}/{source['id']}"
    for method, path in (("GET", _base(knowledge_id)), ("GET", url), ("POST", f"{url}/sync"), ("GET", f"{url}/runs")):
        response = await async_client.request(method, path)
        assert response.status_code in (403, 404), (method, path, response.status_code)

    _act_as(ctx, "dev-alice", "Dev")
    assert (await async_client.get(url)).status_code == 200


async def test_the_deployment_ceilings_cap_what_a_source_may_ask_for(async_client, async_db, ctx, monkeypatch) -> None:
    monkeypatch.setattr(settings, "knowledge_sync_max_items_ceiling", 50)
    knowledge_id = await _knowledge(async_client, async_db, ctx)

    over = await async_client.post(_base(knowledge_id), json=_web_payload(limits={"max_items": 51}))
    ok = await async_client.post(_base(knowledge_id), json=_web_payload(limits={"max_items": 50, "max_item_bytes": 1024}))

    assert over.status_code == 400
    assert ok.status_code == 201
    assert ok.json()["data"]["limits"]["max_items"] == 50 and ok.json()["data"]["limits"]["max_item_bytes"] == 1024
