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
    withheld,
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
