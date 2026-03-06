"""chat_executor

Chat runtime executor for chat.v1 specs.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError
from app.kernel.commons.ids import generate_run_id
from app.kernel.contracts.execution_plan import ExecutionPlan
from app.kernel.events.bus import EventBus
from app.kernel.trace.writer import TraceWriter
from app.modules.workflow.runtime.engine import ExecutionEngine
from app.modules.chat.application.schemas import ChatRagConfig
from app.modules.dataset.application.schemas import QueryRequest, QueryCitation


class ChatExecutorV1:
    """Chat executor that reads runtime config from app_versions.spec_json."""

    def __init__(
        self,
        db: Session,
        ctx: RequestContext,
        *,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.db = db
        self.ctx = ctx
        self.event_bus = event_bus

    def _normalize_model_ref(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if value.startswith("model:"):
            return value
        if ":" in value:
            return f"model:{value}"
        return f"model:{value}"

    def _normalize_rag_spec(self, rag: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not rag or not isinstance(rag, dict):
            return None
        payload = dict(rag)
        if "datasets" in payload and "dataset_ids" not in payload:
            payload["dataset_ids"] = payload.get("datasets")
        return payload

    def _resolve_model_ref(self, spec: Dict[str, Any], inputs: Dict[str, Any]) -> Optional[str]:
        if inputs.get("model"):
            return self._normalize_model_ref(inputs.get("model"))
        if inputs.get("model_ref"):
            return self._normalize_model_ref(inputs.get("model_ref"))

        model_ref = spec.get("model_ref")
        model = spec.get("model")
        if not model_ref:
            if isinstance(model, str):
                model_ref = model
            elif isinstance(model, dict):
                model_ref = model.get("ref_key")
                if not model_ref:
                    provider = model.get("provider")
                    model_name = model.get("model")
                    if provider and model_name:
                        model_ref = f"model:{provider}:{model_name}"
        return self._normalize_model_ref(model_ref) if model_ref else None

    def _resolve_model_params(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        model = spec.get("model")
        if isinstance(model, dict):
            params = model.get("params")
            if isinstance(params, dict):
                return params
        return {}

    def _extract_latest_user_message(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        for msg in reversed(messages):
            if msg.get("role") == "user" and msg.get("content"):
                return str(msg.get("content")).strip()
        return None

    def _format_rag_context(
        self,
        citations: List[QueryCitation],
        fallback_text: Dict[str, str],
    ) -> str:
        if not citations:
            return ""
        lines: List[str] = []
        for idx, citation in enumerate(citations, start=1):
            snippet = citation.snippet or fallback_text.get(citation.chunk_id) or ""
            if not snippet:
                continue
            source = citation.title or citation.doc_key or citation.document_id or citation.chunk_id
            dataset_id = citation.dataset_id or "unknown"
            lines.append(f"[{idx}] {snippet} (source: {source}; dataset: {dataset_id})")
        if not lines:
            return ""
        header = "Use the following dataset snippets to answer the user. Cite sources by [number] when relevant."
        return header + "\n" + "\n".join(lines)

    def _inject_rag_message(self, messages: List[Dict[str, Any]], content: str) -> List[Dict[str, Any]]:
        if not content:
            return messages
        insert_at = 0
        for idx, msg in enumerate(messages):
            if msg.get("role") == "system":
                insert_at = idx + 1
            else:
                break
        injected = dict(role="system", content=content)
        return messages[:insert_at] + [injected] + messages[insert_at:]

    async def _apply_rag(
        self,
        messages: List[Dict[str, Any]],
        rag_spec: Optional[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        if not rag_spec:
            return messages, {}
        payload = self._normalize_rag_spec(rag_spec)
        if not payload:
            return messages, {}
        rag = ChatRagConfig.model_validate(payload)
        if not rag.dataset_ids:
            return messages, {}

        from app.wiring.services import build_dataset_service
        dataset_service = build_dataset_service(db=self.db, ctx=self.ctx)
        query_text = (rag.query or self._extract_latest_user_message(messages) or "").strip()
        if not query_text:
            raise ValidationError("RAG requires rag.query or a user message")

        citations: List[QueryCitation] = []
        fallback_text: Dict[str, str] = {}
        dataset_ids = list(dict.fromkeys([ds for ds in rag.dataset_ids if ds]))
        for dataset_id in dataset_ids:
            query_request = QueryRequest(
                query=query_text,
                top_k=rag.top_k,
                index_id=rag.index_id,
                index_ids=rag.index_ids,
                filter=rag.filter,
                use_rerank=rag.use_rerank,
                reranker_ref=rag.reranker_ref,
                strategy=rag.strategy,
                include_snippets=rag.include_snippets,
                snippet_length=rag.snippet_length,
                max_snippets=rag.max_snippets,
                keyword_top_k=rag.keyword_top_k,
                keyword_candidate_limit=rag.keyword_candidate_limit,
                keyword_min_score=rag.keyword_min_score,
                hybrid_alpha=rag.hybrid_alpha,
            )
            response = await dataset_service.query(dataset_id, query_request)
            for result in response.results:
                if result.text:
                    fallback_text[result.chunk_id] = result.text
            citations.extend(response.citations)

        rag_context = self._format_rag_context(citations, fallback_text)
        messages = self._inject_rag_message(messages, rag_context)
        metadata = {
            "citations": [item.model_dump() for item in citations],
            "rag_query": query_text,
            "rag_datasets": dataset_ids,
        }
        return messages, metadata

    async def execute(
        self,
        *,
        app: Any,
        version: Any,
        inputs: Dict[str, Any],
        spec_override: Optional[Dict[str, Any]] = None,
        mode: str = "chat",
    ) -> Dict[str, Any]:
        spec = spec_override or (version.spec_json or {})
        merged_inputs = dict(inputs or {})
        model_params = self._resolve_model_params(spec)
        limits = spec.get("limits") or {}

        if "temperature" not in merged_inputs and model_params.get("temperature") is not None:
            merged_inputs["temperature"] = model_params.get("temperature")
        if "temperature" not in merged_inputs and spec.get("temperature") is not None:
            merged_inputs["temperature"] = spec.get("temperature")

        if "top_p" not in merged_inputs and model_params.get("top_p") is not None:
            merged_inputs["top_p"] = model_params.get("top_p")
        if "top_p" not in merged_inputs and spec.get("top_p") is not None:
            merged_inputs["top_p"] = spec.get("top_p")

        if "max_tokens" not in merged_inputs and model_params.get("max_tokens") is not None:
            merged_inputs["max_tokens"] = model_params.get("max_tokens")
        if "max_tokens" not in merged_inputs and spec.get("max_tokens") is not None:
            merged_inputs["max_tokens"] = spec.get("max_tokens")
        if "max_tokens" not in merged_inputs and limits.get("max_tokens") is not None:
            merged_inputs["max_tokens"] = limits.get("max_tokens")

        model_ref = self._resolve_model_ref(spec, merged_inputs)
        if model_ref:
            merged_inputs["model"] = model_ref

        messages = list(merged_inputs.get("messages") or [])
        system_prompt = spec.get("system_prompt")
        if system_prompt and not any(msg.get("role") == "system" for msg in messages):
            messages = [{"role": "system", "content": system_prompt}] + messages

        rag_spec = merged_inputs.get("rag") or spec.get("rag")
        messages, rag_meta = await self._apply_rag(messages, rag_spec)
        merged_inputs["messages"] = messages

        if rag_meta:
            merged_inputs.setdefault("metadata", {})
            if isinstance(merged_inputs["metadata"], dict):
                merged_inputs["metadata"].update(rag_meta)

        plan = ExecutionPlan(
            mode=mode,
            inputs=merged_inputs,
            run_id=generate_run_id(),
        )
        plan.app_id = app.id
        plan.app_version_id = version.id
        trace_writer = TraceWriter(self.db, self.ctx, event_bus=self.event_bus)
        engine = ExecutionEngine(self.db, self.ctx, trace_writer=trace_writer)
        result = await engine.execute(plan)
        return {"run_id": plan.run_id, "output": result}
