"""A trace renders as OTLP/JSON: stable ids, parent links, nanosecond times, no content."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.kernel.runtime.db.models.runs import Run, RunStep
from app.kernel.runtime.runs import otlp
from app.kernel.specs import validate_spec

T0 = datetime(2026, 9, 29, 8, 0, 0, 250000, tzinfo=UTC)
PROMPT = "Please refund order 4412 to the customer's card"
ANSWER = "The refund of 120 EUR was issued"
FAILURE = "Provider answered 503: upstream unavailable"


def _run(run_id: str, **overrides) -> Run:
    fields = {
        "id": run_id,
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "trace_id": "trace_01J9KD84QF",
        "mode": "agent",
        "kind": "agent",
        "subject_kind": "agent",
        "subject_id": "agt_refunds",
        "status": "succeeded",
        "input_summary": PROMPT,
        "output_summary": ANSWER,
        "started_at": T0,
        "ended_at": T0 + timedelta(seconds=3),
    }
    fields.update(overrides)
    return Run(**fields)


def _step(record_id: str, run_id: str, **overrides) -> RunStep:
    fields = {
        "id": record_id,
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-a",
        "trace_id": "trace_01J9KD84QF",
        "run_id": run_id,
        "step_type": "llm",
        "status": "succeeded",
        "input_summary": PROMPT,
        "output_summary": ANSWER,
        "started_at": T0 + timedelta(milliseconds=100),
        "ended_at": T0 + timedelta(milliseconds=900),
    }
    fields.update(overrides)
    return RunStep(**fields)


def _trace() -> tuple[list[Run], list[RunStep]]:
    root = _run("run_root")
    child = _run(
        "run_child",
        parent_run_id="run_root",
        mode="tool",
        kind="tool",
        status="failed",
        error_code="tool.timeout",
        error_message=FAILURE,
        started_at=T0 + timedelta(seconds=1),
        ended_at=T0 + timedelta(seconds=2),
    )
    steps = [
        _step(
            "st_answer",
            "run_root",
            step_id="answer",
            metrics_json={
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "latency_ms": 812.5,
                "cached": True,
                "model_ref": "model:test:chat",
                "tool_call": {"name": "refund", "arguments": {"order": "4412"}},
            },
        ),
        _step(
            "st_tool",
            "run_child",
            step_type="tool_call",
            node_id="refund",
            status="failed",
            error_code="tool.timeout",
            error_message=FAILURE,
            error_details={"stderr": FAILURE},
            started_at=T0 + timedelta(seconds=1, milliseconds=50),
            ended_at=None,
        ),
    ]
    return [child, root], steps


def _export() -> dict:
    runs, steps = _trace()
    return otlp.build_trace_export(
        "trace_01J9KD84QF",
        runs,
        steps,
        tenant_id="tenant-a",
        workspace_id="workspace-a",
    )


def _spans(document: dict) -> dict[str, dict]:
    spans = document["resourceSpans"][0]["scopeSpans"][0]["spans"]
    return {
        _attr(span, "soit.run.id")
        if span["name"].startswith("run ")
        else _attr(span, "soit.step.id"): span
        for span in spans
    }


def _attr(span: dict, key: str):
    for item in span["attributes"]:
        if item["key"] == key:
            return next(iter(item["value"].values()))
    return None


def test_the_document_is_the_contract() -> None:
    document = _export()

    assert validate_spec(document, otlp.OTLP_TRACE_SPEC) is True
    resource = {
        item["key"]: next(iter(item["value"].values()))
        for item in document["resourceSpans"][0]["resource"]["attributes"]
    }
    assert resource == {
        "service.name": "soit",
        "soit.tenant.id": "tenant-a",
        "soit.workspace.id": "workspace-a",
        "soit.trace.id": "trace_01J9KD84QF",
    }
    assert document["resourceSpans"][0]["scopeSpans"][0]["scope"] == {"name": "soit"}


def test_ids_are_hex_and_stable() -> None:
    first, second = _export(), _export()
    assert first == second

    spans = _spans(first)
    assert len({span["spanId"] for span in spans.values()}) == 4
    assert all(len(span["spanId"]) == 16 for span in spans.values())
    assert all(
        span["traceId"] == otlp.trace_id_hex("trace_01J9KD84QF")
        for span in spans.values()
    )
    assert spans["run_root"]["spanId"] == otlp.span_id_hex("run_root")


def test_a_hex_trace_id_is_used_as_is_and_any_other_is_hashed() -> None:
    assert (
        otlp.trace_id_hex("4BF92F3577B34DA6A3CE929D0E0E4736")
        == "4bf92f3577b34da6a3ce929d0e0e4736"
    )
    hashed = otlp.trace_id_hex("trace_01J9KD84QF")
    assert len(hashed) == 32 and hashed == otlp.trace_id_hex("trace_01J9KD84QF")
    assert hashed != otlp.trace_id_hex("trace_01J9KD84QG")


def test_runs_nest_under_their_parent_and_steps_under_their_run() -> None:
    spans = _spans(_export())

    assert "parentSpanId" not in spans["run_root"]
    assert spans["run_root"]["kind"] == otlp.SPAN_KIND_SERVER
    assert spans["run_child"]["parentSpanId"] == spans["run_root"]["spanId"]
    assert spans["run_child"]["kind"] == otlp.SPAN_KIND_INTERNAL
    assert spans["st_answer"]["parentSpanId"] == spans["run_root"]["spanId"]
    assert spans["st_tool"]["parentSpanId"] == spans["run_child"]["spanId"]
    assert spans["st_answer"]["kind"] == otlp.SPAN_KIND_CLIENT
    # Parents come before children, oldest first.
    order = [
        span["name"] for span in _export()["resourceSpans"][0]["scopeSpans"][0]["spans"]
    ]
    assert order == ["run agent", "run tool", "llm", "tool_call"]


def test_times_are_nanoseconds_and_an_open_span_ends_where_it_started() -> None:
    spans = _spans(_export())

    assert spans["run_root"]["startTimeUnixNano"] == str(
        int(T0.timestamp()) * 10**9 + 250_000_000
    )
    assert (
        int(spans["run_root"]["endTimeUnixNano"])
        - int(spans["run_root"]["startTimeUnixNano"])
        == 3 * 10**9
    )
    assert (
        int(spans["st_answer"]["endTimeUnixNano"])
        - int(spans["st_answer"]["startTimeUnixNano"])
        == 800 * 10**6
    )
    assert spans["st_tool"]["endTimeUnixNano"] == spans["st_tool"]["startTimeUnixNano"]
    # A naive timestamp is UTC already.
    assert otlp.unix_nano(T0.replace(tzinfo=None)) == otlp.unix_nano(T0)


def test_status_follows_the_record_and_names_the_error_code_only() -> None:
    spans = _spans(_export())

    assert spans["run_root"]["status"] == {"code": otlp.STATUS_OK}
    assert spans["run_child"]["status"] == {
        "code": otlp.STATUS_ERROR,
        "message": "tool.timeout",
    }
    assert spans["st_tool"]["status"] == {
        "code": otlp.STATUS_ERROR,
        "message": "tool.timeout",
    }
    assert otlp.build_trace_export(
        "t",
        [_run("r", status="running", ended_at=None)],
        [],
        tenant_id="a",
        workspace_id="b",
    )["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["status"] == {
        "code": otlp.STATUS_UNSET
    }


def test_attributes_carry_ids_kinds_and_numeric_metrics_and_no_content() -> None:
    document = _export()
    spans = _spans(document)

    assert _attr(spans["run_child"], "soit.run.mode") == "tool"
    assert _attr(spans["run_child"], "soit.run.parent_run_id") == "run_root"
    assert _attr(spans["run_child"], "soit.run.error_code") == "tool.timeout"
    assert _attr(spans["run_root"], "soit.run.attempt_no") == "1"
    assert _attr(spans["st_tool"], "soit.step.node_id") == "refund"
    assert _attr(spans["st_tool"], "soit.step.type") == "tool_call"

    answer = {item["key"]: item["value"] for item in spans["st_answer"]["attributes"]}
    assert answer["soit.step.metric.prompt_tokens"] == {"intValue": "120"}
    assert answer["soit.step.metric.completion_tokens"] == {"intValue": "30"}
    assert answer["soit.step.metric.latency_ms"] == {"doubleValue": 812.5}
    assert not any(key.endswith(("cached", "model_ref", "tool_call")) for key in answer)

    body = json.dumps(document)
    for text in (PROMPT, ANSWER, FAILURE, "4412", "model:test:chat"):
        assert text not in body


def test_a_parent_outside_the_trace_is_not_linked() -> None:
    document = otlp.build_trace_export(
        "t", [_run("r", parent_run_id="elsewhere")], [], tenant_id="a", workspace_id="b"
    )
    span = document["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert "parentSpanId" not in span
    assert _attr(span, "soit.run.parent_run_id") == "elsewhere"
