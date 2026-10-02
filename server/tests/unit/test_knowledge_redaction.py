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
from app.kernel.runtime.runs.knowledge_redaction import (
    KnowledgeRedactor,
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
