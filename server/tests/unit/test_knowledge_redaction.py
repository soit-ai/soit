"""Stored knowledge content is filtered against who may read it now.

The redactor walks stored payloads (citations, knowledge query results, a
workflow's retrieved documents, JSON kept as text) and leaves out every item
naming a document its reader may not read; everything else passes unchanged.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import RunStep
from app.kernel.runtime.runs.content_capture import is_withheld
from app.kernel.runtime.runs.knowledge_redaction import (
    KNOWLEDGE_QUERY_TOOL,
    SOURCES_METRIC,
    KnowledgeRedactor,
    knowledge_sources,
    redact_step_text,
    redact_task_payload,
    redacted_step_rows,
    register_knowledge_read_filter,
    reset_knowledge_read_filter,
)

CTX = RequestContext(tenant_id="t", workspace_id="w", user_id="u_dev", workspace_role="Dev")
SECRET = ("kb_hr", "payroll")


class _Filter:
    """``payroll`` in ``kb_hr`` is unreadable, and so is document ``doc_payroll``."""

    def __init__(self) -> None:
        self.asked: list[tuple[set, set]] = []

    async def unreadable(self, db: Any, ctx: RequestContext, refs: set, document_ids: set) -> tuple[set, set]:
        del db, ctx
        self.asked.append((set(refs), set(document_ids)))
        return {ref for ref in refs if ref == SECRET}, {doc for doc in document_ids if doc in {"doc_payroll", "doc_gone"}}


@pytest.fixture
def read_filter():
    read_filter = _Filter()
    register_knowledge_read_filter(read_filter)
    yield read_filter
    reset_knowledge_read_filter()


def _citation(doc_key: str, **extra: Any) -> dict[str, Any]:
    return {"chunk_id": f"ck_{doc_key}", "document_id": f"doc_{doc_key}", "knowledge_id": "kb_hr", "doc_key": doc_key, "snippet": f"text of {doc_key}", **extra}


def _result(doc_key: str) -> dict[str, Any]:
    return {
        "chunk_id": f"ck_{doc_key}",
        "document_id": f"doc_{doc_key}",
        "text": f"text of {doc_key}",
        "metadata": {"knowledge_id": "kb_hr", "doc_key": doc_key},
    }


@pytest.mark.asyncio
async def test_a_query_result_loses_the_unreadable_document_and_its_total(read_filter) -> None:
    del read_filter
    stored = {
        "result": {
            "results": [_result("travel"), _result("payroll")],
            "total": 2,
            "citations": [_citation("travel"), _citation("payroll")],
        }
    }

    redacted = await KnowledgeRedactor(None, CTX).redact(stored)

    assert [item["metadata"]["doc_key"] for item in redacted["result"]["results"]] == ["travel"]
    assert redacted["result"]["total"] == 1
    assert [item["doc_key"] for item in redacted["result"]["citations"]] == ["travel"]
    assert "payroll" in json.dumps(stored)  # the stored copy itself is untouched


@pytest.mark.asyncio
async def test_a_workflow_retrieve_output_rebuilds_its_context(read_filter) -> None:
    del read_filter
    output = {
        "context": "text of travel\n\ntext of payroll",
        "documents": [_result("travel"), _result("payroll")],
        "citations": [_citation("travel"), _citation("payroll")],
        "count": 2,
    }

    redacted = await KnowledgeRedactor(None, CTX).redact(output)

    assert redacted["context"] == "text of travel"
    assert redacted["count"] == 1
    assert len(redacted["citations"]) == 1


@pytest.mark.asyncio
async def test_a_single_citation_outside_a_list_is_withheld(read_filter) -> None:
    del read_filter
    event = {"type": "CUSTOM", "name": "soit.source", "value": {"schemaVersion": 1, **_citation("payroll")}}

    redacted = await KnowledgeRedactor(None, CTX).redact(event)

    assert set(redacted["value"]) == {"withheld"}
    assert "payroll" not in json.dumps(redacted)


@pytest.mark.asyncio
async def test_json_kept_as_text_is_filtered_too(read_filter) -> None:
    del read_filter
    event = {"type": "TOOL_CALL_RESULT", "content": json.dumps({"citations": [_citation("travel"), _citation("payroll")]})}

    redacted = await KnowledgeRedactor(None, CTX).redact(event)

    assert [item["doc_key"] for item in json.loads(redacted["content"])["citations"]] == ["travel"]


@pytest.mark.asyncio
async def test_an_old_citation_is_judged_by_its_document_id(read_filter) -> None:
    del read_filter
    old = [
        {"chunk_id": "ck_1", "document_id": "doc_payroll", "snippet": "salary"},
        {"chunk_id": "ck_2", "document_id": "doc_gone", "snippet": "deleted"},
        {"chunk_id": "ck_3", "document_id": "doc_travel", "snippet": "trips"},
    ]

    redacted = await KnowledgeRedactor(None, CTX).redact(old)

    assert [item["document_id"] for item in redacted] == ["doc_travel"]


@pytest.mark.asyncio
async def test_content_naming_no_knowledge_document_passes_unchanged(read_filter) -> None:
    provider_citations = [{"type": "url", "title": "Docs", "url": "https://example.com"}]
    redactor = KnowledgeRedactor(None, CTX)

    assert await redactor.redact(provider_citations) is provider_citations
    assert await redactor.redact("plain answer text") == "plain answer text"
    assert read_filter.asked == []


@pytest.mark.asyncio
async def test_one_reader_asks_once_per_document(read_filter) -> None:
    redactor = KnowledgeRedactor(None, CTX)

    await redactor.redact([_citation("travel"), _citation("payroll")])
    await redactor.redact({"citations": [_citation("payroll")]})

    assert len(read_filter.asked) == 1


@pytest.mark.asyncio
async def test_without_a_filter_nothing_is_touched() -> None:
    stored = [_citation("payroll")]

    assert await KnowledgeRedactor(None, CTX).redact(stored) is stored


class _RestrictingFilter(_Filter):
    """As ``_Filter``; ``kb_hr`` holds a document the reader may not read, ``kb_open`` none."""

    def __init__(self) -> None:
        super().__init__()
        self.restricts_asked: list[str | None] = []

    async def restricts(self, db: Any, ctx: RequestContext, knowledge_id: str | None) -> bool:
        del db, ctx
        self.restricts_asked.append(knowledge_id)
        return knowledge_id in {None, "kb_hr"}


@pytest.fixture
def restricting_filter():
    read_filter = _RestrictingFilter()
    register_knowledge_read_filter(read_filter)
    yield read_filter
    reset_knowledge_read_filter()


def _knowledge_tool_metrics(*doc_keys: str, knowledge_id: str = "kb_hr") -> dict[str, Any]:
    return {
        "tool_call": {
            "tool_ref": KNOWLEDGE_QUERY_TOOL,
            "arguments": {"knowledge_id": knowledge_id, "query": "pay"},
            "result": {"results": [_result(key) for key in doc_keys], "total": len(doc_keys)},
        }
    }


@pytest.mark.asyncio
async def test_a_knowledge_tool_summary_is_withheld_when_its_result_names_an_unreadable_document(read_filter) -> None:
    del read_filter
    metrics = _knowledge_tool_metrics("travel", "payroll")

    summary, out = await redact_step_text(KnowledgeRedactor(None, CTX), "Salaries are 10k a month", metrics)

    assert is_withheld(summary)
    assert out["tool_call"]["result"]["total"] == 1
    assert metrics["tool_call"]["result"]["total"] == 2


@pytest.mark.asyncio
async def test_a_step_summary_from_readable_documents_is_kept(read_filter) -> None:
    del read_filter
    summary, _ = await redact_step_text(KnowledgeRedactor(None, CTX), "Trips are booked", _knowledge_tool_metrics("travel"))

    assert summary == "Trips are booked"


@pytest.mark.asyncio
async def test_a_workflow_step_is_judged_by_its_recorded_sources(read_filter) -> None:
    del read_filter
    redactor = KnowledgeRedactor(None, CTX)
    output = {"context": "text of payroll", "documents": [_result("payroll")], "count": 1}
    sources = knowledge_sources(output)

    denied, _ = await redact_step_text(redactor, str(output), {"node_type": "retrieve", SOURCES_METRIC: sources})
    kept, _ = await redact_step_text(redactor, "text of travel", {SOURCES_METRIC: [["kb_hr", "travel"]]})

    assert sources == [["kb_hr", "payroll"]]
    assert is_withheld(denied)
    assert kept == "text of travel"


@pytest.mark.asyncio
async def test_a_json_summary_is_filtered_rather_than_withheld(read_filter) -> None:
    del read_filter
    summary = json.dumps({"citations": [_citation("travel"), _citation("payroll")]})

    out, _ = await redact_step_text(KnowledgeRedactor(None, CTX), summary, {SOURCES_METRIC: [list(SECRET)]})

    assert [item["doc_key"] for item in json.loads(out)["citations"]] == ["travel"]


@pytest.mark.asyncio
async def test_a_step_recorded_before_sources_falls_back_to_its_knowledge_base(restricting_filter) -> None:
    redactor = KnowledgeRedactor(None, CTX)
    truncated = {"truncated": True, "size_bytes": 99999, "payload_hash": "h"}

    restricted_tool, _ = await redact_step_text(
        redactor, "some text", {"tool_call": {"tool_ref": KNOWLEDGE_QUERY_TOOL, "arguments": {"knowledge_id": "kb_hr"}, "result": truncated}}
    )
    open_tool, _ = await redact_step_text(
        redactor, "some text", {"tool_call": {"tool_ref": KNOWLEDGE_QUERY_TOOL, "arguments": {"knowledge_id": "kb_open"}}}
    )
    old_retrieve, _ = await redact_step_text(redactor, "some text", {"node_type": "retrieve"})
    llm, _ = await redact_step_text(redactor, "some text", {"node_type": "llm"})

    assert is_withheld(restricted_tool)
    assert open_tool == "some text"
    assert is_withheld(old_retrieve)
    assert llm == "some text"
    assert restricting_filter.restricts_asked == ["kb_hr", "kb_open", None]


@pytest.mark.asyncio
async def test_step_rows_are_copied_never_changed(read_filter) -> None:
    del read_filter
    rows = [
        RunStep(id="s1", tenant_id="t", workspace_id="w", run_id="r", step_type="tool", status="succeeded",
                output_summary="Salaries", metrics_json=_knowledge_tool_metrics("payroll")),
        RunStep(id="s2", tenant_id="t", workspace_id="w", run_id="r", step_type="llm", status="succeeded", output_summary="Hello"),
    ]

    out = await redacted_step_rows(KnowledgeRedactor(None, CTX), rows)

    assert is_withheld(out[0].output_summary)
    assert out[0] is not rows[0] and rows[0].output_summary == "Salaries"
    assert out[1] is rows[1]


@pytest.mark.asyncio
async def test_an_approval_checkpoint_withholds_its_retrieved_context(read_filter) -> None:
    del read_filter
    progress = {
        "phase": "waiting_approval",
        "checkpoint": {
            "messages": [{"role": "user", "content": "what are salaries"}],
            "rag_context": "text of payroll",
            "citations": [_citation("travel"), _citation("payroll")],
            "iterations": 1,
        },
    }
    readable = {"checkpoint": {"rag_context": "text of travel", "citations": [_citation("travel")]}}
    redactor = KnowledgeRedactor(None, CTX)

    out = await redact_task_payload(redactor, progress)

    checkpoint = out["checkpoint"]
    assert is_withheld(checkpoint["rag_context"])
    assert set(checkpoint["messages"]) == {"withheld"}
    assert [item["doc_key"] for item in checkpoint["citations"]] == ["travel"]
    assert checkpoint["iterations"] == 1
    assert progress["checkpoint"]["rag_context"] == "text of payroll"
    assert await redact_task_payload(redactor, readable) is readable
