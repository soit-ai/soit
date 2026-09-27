"""metadata_only keeps lengths and hashes of run text, never the text itself."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs.content_capture import (
    CAPTURE_FULL,
    CAPTURE_METADATA_ONLY,
    ContentCapture,
    get_workspace_capture_lookup,
    register_workspace_capture_lookup,
    reset_workspace_capture_lookup,
    stricter_capture,
    url_origin,
    withheld,
    withheld_object,
)
from app.kernel.runtime.runs.writer import TraceWriter
from app.modules.identity.domain.models import Workspace
from app.modules.identity.infra.content_capture import workspace_content_capture

SECRET = "the launch code is 0451"


@pytest.fixture
def restore_lookup() -> Iterator[None]:
    original = get_workspace_capture_lookup()
    yield
    if original is None:
        reset_workspace_capture_lookup()
    else:
        register_workspace_capture_lookup(original)


def test_withheld_text_keeps_only_its_length_and_a_hash() -> None:
    marker = withheld(SECRET)

    assert SECRET not in marker
    assert marker.startswith(f"[withheld: {len(SECRET)} chars, sha256:")
    assert withheld(SECRET) == marker


def test_the_stricter_mode_wins() -> None:
    assert stricter_capture(CAPTURE_FULL, None) == CAPTURE_FULL
    assert stricter_capture(CAPTURE_FULL, CAPTURE_METADATA_ONLY) == CAPTURE_METADATA_ONLY
    assert stricter_capture(None, CAPTURE_METADATA_ONLY) == CAPTURE_METADATA_ONLY


def test_error_details_keep_their_structure_and_lose_their_text() -> None:
    capture = ContentCapture(CAPTURE_METADATA_ONLY)

    details = capture.details(
        {"error_type": "BadRequestError", "code": "X", "status_code": 400, "detail": SECRET, "echo": [SECRET]}
    )

    assert details is not None
    assert (details["error_type"], details["code"], details["status_code"]) == ("BadRequestError", "X", 400)
    assert SECRET not in str(details)
    assert ContentCapture(CAPTURE_FULL).details({"detail": SECRET}) == {"detail": SECRET}


@pytest.mark.asyncio
async def test_a_metadata_only_writer_stores_no_run_text(async_db, ctx: RequestContext) -> None:
    writer = TraceWriter(async_db, replace(ctx, content_capture=CAPTURE_METADATA_ONLY))

    run = await writer.create_run("gateway", input_summary=SECRET)
    step = await writer.create_step(run.id, "llm", input_summary=SECRET, status="running")
    await writer.update_step_status(
        step.id, "failed", output_summary=SECRET, error_message=SECRET, error_details={"detail": SECRET}
    )
    await writer.update_run_status(run.id, "failed", output_summary=SECRET, error_message=SECRET)
    await async_db.commit()

    stored_run = await async_db.get(Run, run.id)
    stored_step = await async_db.get(RunStep, step.id)
    stored = " ".join(
        str(value)
        for value in (
            stored_run.input_summary,
            stored_run.output_summary,
            stored_run.error_message,
            stored_step.input_summary,
            stored_step.output_summary,
            stored_step.error_message,
            stored_step.error_details,
        )
    )
    assert SECRET not in stored
    assert stored_run.input_summary == withheld(SECRET)
    assert stored_run.status == "failed"


@pytest.mark.asyncio
@pytest.mark.usefixtures("restore_lookup")
async def test_a_worker_context_reads_the_workspace_setting(async_db, ctx: RequestContext) -> None:
    async_db.add(
        Workspace(
            id=ctx.workspace_id,
            tenant_id=ctx.tenant_id,
            name="private",
            content_capture=CAPTURE_METADATA_ONLY,
        )
    )
    await async_db.commit()
    register_workspace_capture_lookup(workspace_content_capture)

    writer = TraceWriter(async_db, ctx)
    run = await writer.create_run("agent", input_summary=SECRET)

    assert (await writer.content_capture()).mode == CAPTURE_METADATA_ONLY
    assert run.input_summary == withheld(SECRET)


@pytest.mark.asyncio
@pytest.mark.usefixtures("restore_lookup")
async def test_a_failed_lookup_withholds_content(async_db, ctx: RequestContext) -> None:
    async def broken(*_args: object) -> str | None:
        raise ConnectionError("lookup failed")

    register_workspace_capture_lookup(broken)

    run = await TraceWriter(async_db, ctx).create_run("agent", input_summary=SECRET)

    assert run.input_summary == withheld(SECRET)


@pytest.mark.asyncio
@pytest.mark.usefixtures("restore_lookup")
async def test_without_a_setting_content_is_kept(async_db, ctx: RequestContext) -> None:
    register_workspace_capture_lookup(workspace_content_capture)

    run = await TraceWriter(async_db, ctx).create_run("agent", input_summary=SECRET)

    assert run.input_summary == SECRET



def test_withholding_again_changes_nothing() -> None:
    # Records are written, read back and written again; a marker must not
    # become a marker of itself.
    capture = ContentCapture(CAPTURE_METADATA_ONLY)
    metrics = {"tool_call": {"arguments": {"q": SECRET, "n": 7}, "error_message": SECRET}}

    once = capture.metrics(metrics)

    assert capture.metrics(once) == once
    assert withheld(withheld(SECRET)) == withheld(SECRET)
    assert withheld_object(withheld_object({"q": SECRET})) == withheld_object({"q": SECRET})


def test_tool_call_metrics_keep_their_shape_and_identifiers_only() -> None:
    capture = ContentCapture(CAPTURE_METADATA_ONLY)

    kept = capture.metrics(
        {
            "latency_ms": 12,
            "tool_call": {
                "tool_ref": "tool:http:request",
                "tool_type": "http",
                "status": "completed",
                "arguments": {"url": f"https://api.example.com/search?q={SECRET}", "limit": 77310413},
                "result": {"result": {"answer": SECRET}},
                "metadata": {"workflow_run_id": "wfr_0123456789abcdef", "headers": {"x-auth": {"secret_id": "sec_abc"}}},
                "error_code": None,
                "error_message": SECRET,
            },
            "egress": {"decision": "allow", "url": f"https://api.example.com/search?q={SECRET}"},
            "content": [{"type": "text", "text": SECRET}],
            "content_safety": [{"provider": "http", "findings": [{"category": "pii", "detail": SECRET}]}],
        }
    )

    assert SECRET not in str(kept) and "77310413" not in str(kept)
    call = kept["tool_call"]
    assert (call["tool_ref"], call["status"]) == ("tool:http:request", "completed")
    assert set(call["arguments"]) == {"url", "limit"}
    assert call["arguments"]["url"] == "https://api.example.com"
    # Identifiers stay: child runs and secret references are still found.
    assert call["metadata"]["workflow_run_id"] == "wfr_0123456789abcdef"
    assert call["metadata"]["headers"]["x-auth"] == {"secret_id": "sec_abc"}
    assert kept["egress"] == {"decision": "allow", "url": "https://api.example.com"}
    assert kept["latency_ms"] == 12
    assert kept["content_safety"][0]["findings"][0]["category"] == "pii"
    assert ContentCapture(CAPTURE_FULL).metrics({"tool_call": {"arguments": {"q": SECRET}}}) == {
        "tool_call": {"arguments": {"q": SECRET}}
    }


def test_a_url_keeps_only_where_it_went() -> None:
    assert url_origin("https://user:pw@api.example.com:8443/p?q=1#f") == "https://api.example.com:8443"
    assert url_origin("not a url") == withheld("not a url")


@pytest.mark.asyncio
async def test_a_metadata_only_writer_stores_no_tool_content(async_db, ctx: RequestContext) -> None:
    from sqlmodel import select

    from app.kernel.runtime.db.models.audit import AuditEvent

    writer = TraceWriter(async_db, replace(ctx, content_capture=CAPTURE_METADATA_ONLY))
    run = await writer.create_run("tool")
    step = await writer.create_step(run.id, "tool", status="running")
    tool_call = {"tool_ref": "tool:function:echo", "arguments": {"text": SECRET}, "result": {"result": SECRET}}

    await writer.update_step_metrics(step.id, {"tool_call": tool_call})
    await writer.update_step_status(step.id, "succeeded", metrics={"tool_call": tool_call, "latency_ms": 3})
    await writer.record_audit(
        run_id=run.id,
        step_id=step.id,
        gateway_type="tool",
        outcome="succeeded",
        payload={"gateway_type": "tool", "request": {"parameters": {"text": SECRET}}, "tool_ref": "tool:function:echo"},
    )
    await async_db.commit()

    stored = await async_db.get(RunStep, step.id)
    audits = (await async_db.exec(select(AuditEvent).where(AuditEvent.run_id == run.id))).all()
    assert SECRET not in str(stored.metrics_json)
    assert stored.metrics_json["tool_call"]["tool_ref"] == "tool:function:echo"
    assert stored.metrics_json["latency_ms"] == 3
    assert SECRET not in str([audit.payload_json for audit in audits])
    assert audits[0].payload_json["tool_ref"] == "tool:function:echo"


@pytest.mark.asyncio
async def test_a_metadata_only_audit_does_not_spill_content_to_storage(async_db, ctx: RequestContext) -> None:
    from app.kernel.ports.common.audit import log_gateway_request

    class _Storage:
        def __init__(self) -> None:
            self.puts: list[bytes] = []

        async def put(self, key, data, **kwargs):
            self.puts.append(data)

    writer = TraceWriter(async_db, replace(ctx, content_capture=CAPTURE_METADATA_ONLY))
    run = await writer.create_run("tool")
    step = await writer.create_step(run.id, "tool", status="running")
    storage = _Storage()

    await log_gateway_request(
        writer,
        run.id,
        step.id,
        "tool",
        {"parameters": {"text": SECRET * 1000}},
        {"success": True, "result": SECRET * 1000},
        storage_port=storage,
    )

    assert all(SECRET.encode() not in data for data in storage.puts)


def test_only_identifiers_are_spread_from_a_content_free_record() -> None:
    # An MCP tool's metadata carries its output; a step keeps its ids only.
    metadata = {"server_id": "srv_1", "content": [{"type": "text", "text": SECRET}], "isError": False}

    assert ContentCapture(CAPTURE_METADATA_ONLY).identifiers(metadata) == {"server_id": "srv_1"}
    assert ContentCapture(CAPTURE_FULL).identifiers(metadata) == metadata



def test_what_a_call_handled_is_withheld_whatever_its_keys_are_called() -> None:
    # A tool's argument named "code" or a result field named "status" is
    # content, not the record's own status.
    capture = ContentCapture(CAPTURE_METADATA_ONLY)
    call = {
        "tool_ref": "tool:mcp:runner",
        "status": "completed",
        "arguments": {"code": SECRET, "source": SECRET, "id": SECRET},
        "result": {"status": SECRET, "category": SECRET, "workflow_run_id": "wfr_0123456789abcdef"},
    }

    metrics = capture.metrics({"tool_call": call})
    audit = capture.audit_payload(
        {"gateway_type": "tool", "request": {"tool_ref": "tool:mcp:runner", "parameters": {"code": SECRET}}}
    )

    assert SECRET not in str(metrics) and SECRET not in str(audit)
    assert metrics["tool_call"]["status"] == "completed"
    assert metrics["tool_call"]["result"]["workflow_run_id"] == "wfr_0123456789abcdef"
    assert audit["request"]["tool_ref"] == "tool:mcp:runner"


def test_a_retrievals_query_is_withheld_with_its_counts_kept() -> None:
    metrics = ContentCapture(CAPTURE_METADATA_ONLY).metrics(
        {"knowledge_id": "kb_1", "query": SECRET, "top_k": 3, "avg_score": 0.5, "model_ref": "model:test:m"}
    )

    assert metrics["query"] == withheld(SECRET)
    assert (metrics["knowledge_id"], metrics["top_k"], metrics["avg_score"]) == ("kb_1", 3, 0.5)
    assert metrics["model_ref"] == "model:test:m"


@pytest.mark.parametrize("url", ["https://h:99999/x", "http://h:80:80/", "http://[::1/x", "https://h:port/"])
def test_a_url_that_cannot_be_read_is_withheld_not_raised(url) -> None:
    capture = ContentCapture(CAPTURE_METADATA_ONLY)

    assert url_origin(url) == withheld(url)
    assert capture.metrics({"tool_call": {"arguments": {"url": url}}})["tool_call"]["arguments"]["url"] == withheld(url)
    assert capture.audit_payload({"request": {"egress": {"url": url}}})["request"]["egress"]["url"] == withheld(url)


def test_a_url_given_by_reference_keeps_its_reference() -> None:
    # A webhook kept as a secret is called with {"url": {"secret_id": ...}};
    # the secret boundary evidence reads that reference.
    capture = ContentCapture(CAPTURE_METADATA_ONLY)
    arguments = {"url": {"secret_id": "sec_hook"}, "body": SECRET}

    metrics = capture.metrics({"tool_call": {"arguments": arguments}})
    audit = capture.audit_payload({"request": {"parameters": arguments}})

    assert metrics["tool_call"]["arguments"]["url"] == {"secret_id": "sec_hook"}
    assert audit["request"]["parameters"]["url"] == {"secret_id": "sec_hook"}
    assert SECRET not in str(metrics) + str(audit)


def test_a_reference_named_field_is_kept_only_when_it_holds_an_id() -> None:
    capture = ContentCapture(CAPTURE_METADATA_ONLY)
    payload = {
        "task_id": "summarise the patient notes",
        "prior_run_id": SECRET,
        "workflow_run_id": "wfr_0123456789abcdef",
        "run_id": "run_0123456789abcdef",
    }

    kept = capture.metrics({"tool_call": {"result": payload}})["tool_call"]["result"]

    assert kept["workflow_run_id"] == "wfr_0123456789abcdef"
    assert kept["run_id"] == "run_0123456789abcdef"
    assert kept["task_id"] == withheld("summarise the patient notes")
    assert kept["prior_run_id"] == withheld(SECRET)
