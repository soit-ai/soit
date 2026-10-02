"""Copies of knowledge content, filtered by who may read them now.

Retrieval leaves out documents the caller may not read, but runs keep what
earlier retrievals returned: citations, knowledge query results, a workflow's
retrieved documents. When such a copy is read back it is filtered against the
reader's current access, so a document restricted after it was retrieved, or
retrieved by someone who could read it, is not handed to someone who cannot.

Items name their document by ``knowledge_id`` and ``doc_key`` (at the top
level, or under ``metadata`` for query results), or, in older copies, only by
``document_id``. In a list, an item the reader may not read is dropped; an
item anywhere else is replaced by a withheld marker. Totals and a workflow's
joined ``context`` are recomputed from what remains. Items that name no
knowledge document, such as a model provider's URL citations, pass unchanged.

The kernel only walks the payloads; which documents a reader may not read is
answered by the knowledge module through a registered filter.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.runs.content_capture import (
    is_withheld,
    withheld,
    withheld_object,
)

DocumentRef = tuple[str, str]
"""(knowledge_id, doc_key)."""

KNOWLEDGE_QUERY_TOOL = "tool:function:knowledge_query"
SOURCES_METRIC = "knowledge_documents"
"""Step metric listing the documents a step's output came from, as [knowledge_id, doc_key]."""


class KnowledgeReadFilter(Protocol):
    async def unreadable(
        self,
        db: Any,
        ctx: RequestContext,
        refs: set[DocumentRef],
        document_ids: set[str],
    ) -> tuple[set[DocumentRef], set[str]]:
        """Of ``refs`` and ``document_ids``, those ``ctx`` may not read now.

        A document id that names no document is readable: there is nothing
        left to enforce on it.
        """
        ...

    async def restricts(self, db: Any, ctx: RequestContext, knowledge_id: str | None) -> bool:
        """Whether ``ctx`` may not read some document of a knowledge base, or of any if None.

        For text whose documents are not known: withheld when this is true.
        """
        ...


_read_filter: KnowledgeReadFilter | None = None


def register_knowledge_read_filter(read_filter: KnowledgeReadFilter) -> None:
    global _read_filter
    _read_filter = read_filter


def reset_knowledge_read_filter() -> None:
    global _read_filter
    _read_filter = None


def get_knowledge_read_filter() -> KnowledgeReadFilter | None:
    return _read_filter


def _str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _identity(item: dict[str, Any]) -> tuple[DocumentRef | None, str | None]:
    """The document an item names: by (knowledge_id, doc_key), else by document_id."""
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    knowledge_id = _str(item.get("knowledge_id")) or _str(metadata.get("knowledge_id"))
    doc_key = _str(item.get("doc_key")) or _str(metadata.get("doc_key"))
    if knowledge_id and doc_key:
        return (knowledge_id, doc_key), None
    document_id = _str(item.get("document_id"))
    # A bare document_id only counts on something shaped like retrieved content.
    if document_id and ("chunk_id" in item or "snippet" in item or "text" in item):
        return None, document_id
    return None, None


def _maybe_json(value: str) -> Any:
    text = value.strip()
    if not text or text[0] not in "[{" or ("doc_key" not in text and "document_id" not in text):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _collect(value: Any, refs: set[DocumentRef], ids: set[str]) -> None:
    """Every document ``value`` names, into ``refs`` or, by document_id only, ``ids``."""
    if isinstance(value, dict):
        ref, document_id = _identity(value)
        if ref:
            refs.add(ref)
        elif document_id:
            ids.add(document_id)
        for child in value.values():
            _collect(child, refs, ids)
    elif isinstance(value, list):
        for child in value:
            _collect(child, refs, ids)
    elif isinstance(value, str):
        parsed = _maybe_json(value)
        if parsed is not None:
            _collect(parsed, refs, ids)


class KnowledgeRedactor:
    """Filters payloads for one reader; asks the knowledge module once per new document."""

    def __init__(self, db: Any, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx
        self._read_filter = get_knowledge_read_filter()
        self._denied_refs: set[DocumentRef] = set()
        self._denied_ids: set[str] = set()
        self._known_refs: set[DocumentRef] = set()
        self._known_ids: set[str] = set()

    async def _learn(self, value: Any) -> bool:
        """Ask about documents not asked about yet; whether any named document is denied."""
        refs: set[DocumentRef] = set()
        ids: set[str] = set()
        _collect(value, refs, ids)
        if not refs and not ids:
            return False
        new_refs = refs - self._known_refs
        new_ids = ids - self._known_ids
        if new_refs or new_ids:
            denied_refs, denied_ids = await self._read_filter.unreadable(  # type: ignore[union-attr]
                self.db, self.ctx, new_refs, new_ids
            )
            self._denied_refs |= denied_refs
            self._denied_ids |= denied_ids
            self._known_refs |= new_refs
            self._known_ids |= new_ids
        return bool(refs & self._denied_refs or ids & self._denied_ids)

    def _denied(self, item: dict[str, Any]) -> bool:
        ref, document_id = _identity(item)
        if ref:
            return ref in self._denied_refs
        return bool(document_id and document_id in self._denied_ids)

    def _filter(self, value: Any) -> Any:
        if isinstance(value, list):
            return [
                self._filter(child)
                for child in value
                if not (isinstance(child, dict) and self._denied(child))
            ]
        if isinstance(value, dict):
            if self._denied(value):
                return withheld_object(value)
            out = {key: self._filter(child) for key, child in value.items()}
            if isinstance(out.get("results"), list) and isinstance(out.get("total"), int):
                out["total"] = len(out["results"])
            documents = out.get("documents")
            before = value.get("documents")
            if isinstance(documents, list) and isinstance(before, list) and len(documents) != len(before):
                # A workflow's retrieve output: its context is the documents' text joined.
                if isinstance(out.get("context"), str):
                    out["context"] = "\n\n".join(
                        str(doc.get("text") or "") for doc in documents if isinstance(doc, dict)
                    )
                if isinstance(out.get("count"), int):
                    out["count"] = len(documents)
            return out
        if isinstance(value, str):
            parsed = _maybe_json(value)
            if parsed is not None:
                return json.dumps(self._filter(parsed), ensure_ascii=False, default=str)
        return value

    async def redact(self, value: Any) -> Any:
        """``value`` with the knowledge content its reader may not read removed."""
        if self._read_filter is None or value is None:
            return value
        if not await self._learn(value):
            return value
        return self._filter(value)

    async def denies_any(self, value: Any) -> bool:
        """Whether ``value`` names a document its reader may not read."""
        if self._read_filter is None or value is None:
            return False
        return await self._learn(value)


def knowledge_sources(value: Any) -> list[list[str]]:
    """The documents ``value`` names, as sorted [knowledge_id, doc_key] pairs, for a step's metrics."""
    refs: set[DocumentRef] = set()
    _collect(value, refs, set())
    return [list(ref) for ref in sorted(refs)]


async def redact_step_text(
    redactor: KnowledgeRedactor,
    output_summary: str | None,
    metrics: dict[str, Any] | None,
) -> tuple[str | None, dict[str, Any] | None]:
    """A step's output summary and metrics as their reader may read them now.

    Structured copies in the metrics are filtered item by item. The summary is
    text: kept, filtered when it is JSON, or withheld whole when it came from a
    document the reader may not read. Where a knowledge step recorded no
    sources (steps written before sources were kept), it is withheld when the
    reader may not read some document of the knowledge base, or of any.
    """
    if redactor._read_filter is None:
        return output_summary, metrics
    metrics_out = await redactor.redact(metrics) if metrics else metrics
    values = metrics if isinstance(metrics, dict) else {}
    tool_call = values.get("tool_call") if isinstance(values.get("tool_call"), dict) else {}
    knowledge_tool = tool_call.get("tool_ref") == KNOWLEDGE_QUERY_TOOL
    sources = values.get(SOURCES_METRIC)
    structured = tool_call.get("result") if isinstance(tool_call.get("result"), dict | list) else None
    if isinstance(structured, dict) and set(structured) <= {"truncated", "size_bytes", "payload_hash"}:
        # Too large to keep: a stub holding no content, and no sources either.
        structured = None

    deny = False
    known = False
    if isinstance(sources, list):
        known = True
        named = [
            {"knowledge_id": pair[0], "doc_key": pair[1]}
            for pair in sources
            if isinstance(pair, list | tuple) and len(pair) == 2
        ]
        deny = await redactor.denies_any(named)
    if not deny and structured is not None:
        known = known or knowledge_tool
        deny = await redactor.denies_any(structured)
    if not deny and not known and (knowledge_tool or values.get("node_type") == "retrieve"):
        arguments = tool_call.get("arguments") if isinstance(tool_call.get("arguments"), dict) else {}
        knowledge_id = arguments.get("knowledge_id") if knowledge_tool else None
        restricts = getattr(redactor._read_filter, "restricts", None)
        if restricts is not None:
            deny = await restricts(redactor.db, redactor.ctx, knowledge_id if isinstance(knowledge_id, str) else None)

    summary = output_summary
    if isinstance(summary, str) and summary and not is_withheld(summary):
        parsed = _maybe_json(summary)
        if parsed is not None:
            summary = await redactor.redact(summary)
        elif deny:
            summary = withheld(summary)
    return summary, metrics_out


async def redacted_step_rows(redactor: KnowledgeRedactor, steps: list[Any]) -> list[Any]:
    """Stored step rows as their reader may read them now, as detached copies.

    A row that changes is copied, never edited, so nothing written back to the
    session alters what was recorded.
    """
    out: list[Any] = []
    for step in steps:
        summary, metrics = await redact_step_text(redactor, step.output_summary, step.metrics_json)
        if summary is step.output_summary and metrics is step.metrics_json:
            out.append(step)
        else:
            out.append(type(step).model_validate({**step.model_dump(), "output_summary": summary, "metrics_json": metrics}))
    return out


async def redact_task_payload(redactor: KnowledgeRedactor, value: Any) -> Any:
    """A task's input, output, progress or event payload as its reader may read it now.

    Citations are filtered item by item. An agent's approval checkpoint also
    keeps the retrieved context and the conversation as text: those are
    withheld whole when its citations name a document the reader may not read.
    """
    if not isinstance(value, dict):
        return await redactor.redact(value)
    redacted = await redactor.redact(value)
    for holder_key in (None, "progress"):
        source = value if holder_key is None else value.get(holder_key)
        target = redacted if holder_key is None else (redacted.get(holder_key) if isinstance(redacted, dict) else None)
        if not isinstance(source, dict) or not isinstance(target, dict):
            continue
        checkpoint = source.get("checkpoint")
        out_checkpoint = target.get("checkpoint")
        if not isinstance(checkpoint, dict) or not isinstance(out_checkpoint, dict):
            continue
        if not await redactor.denies_any(checkpoint.get("citations")):
            continue
        out_checkpoint = dict(out_checkpoint)
        if isinstance(checkpoint.get("rag_context"), str) and checkpoint["rag_context"]:
            out_checkpoint["rag_context"] = withheld(checkpoint["rag_context"])
        if checkpoint.get("messages"):
            out_checkpoint["messages"] = withheld_object(checkpoint["messages"])
        target = dict(target)
        target["checkpoint"] = out_checkpoint
        if holder_key is None:
            redacted = target
        else:
            redacted = {**redacted, holder_key: target}
    return redacted


async def redact_knowledge(db: Any, ctx: RequestContext, value: Any) -> Any:
    """One-off :meth:`KnowledgeRedactor.redact`."""
    return await KnowledgeRedactor(db, ctx).redact(value)
