"""Run deterministic support/ticket regression checks for the Enterprise MVP."""

from __future__ import annotations

import argparse
import asyncio
import copy
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import and_, select

from app.adapters.tools.router import RegistryToolRouterPort
from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    EmbeddingResponse,
    LLMPort,
    RerankResponse,
    ToolCall,
)
from app.kernel.registry.deps import get_registry
from app.kernel.runtime.runs.service import RunService
from app.modules.agent.application.application_service import AgentApplicationService
from app.modules.agent.application.schemas import AgentRunRequest
from app.modules.knowledge.application.runtime_schemas import QueryRequest
from app.modules.knowledge.domain.models import KnowledgeIndex
from app.modules.knowledge.runtime import tool_entrypoint as knowledge_tools
from app.wiring.container import reset_container
from app.wiring.services import build_knowledge_runtime_service, build_response_service
from scripts.bootstrap_enterprise_mvp import BootstrapResult, bootstrap_enterprise_mvp

DEFAULT_CASES_PATH = Path(__file__).resolve().parent / "support_ticket_golden_set.json"
DEMO_TICKET_TOOL_REF = "builtin.ticket.create_review_ticket"


@dataclass
class SupportTicketGoldenCase:
    case_id: str
    prompt: str
    expected_citation_source: str
    expect_tool_call: bool
    expect_workflow_child_run: bool
    expect_audit: bool
    minimum_answer_terms: list[str] = field(default_factory=list)


@dataclass
class SupportTicketCaseReport:
    case_id: str
    passed: bool
    failure_reasons: list[str]
    prompt: str
    output: str
    run_id: str | None
    response_id: str | None
    thread_id: str | None
    expected_citation_source: str
    tool_call_count: int
    citation_count: int
    audit_count: int
    child_run_count: int
    latency_ms: int
    cost: dict[str, Any]
    run_explorer_url: str | None
    governance_evidence: list[dict[str, Any]] = field(default_factory=list)
    governance_passed: bool = False
    governance_failures: list[str] = field(default_factory=list)


class SupportTicketEvaluationLLMPort(LLMPort):
    """Deterministic evaluator LLM used only by the regression runner."""

    def __init__(self, case: SupportTicketGoldenCase, *, workflow_ref: str, workflow_inputs: dict[str, Any]) -> None:
        self.case = case
        self.workflow_ref = workflow_ref
        self.workflow_inputs = workflow_inputs
        self._called_tool = False

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        *,
        tools=None,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        prompt_tokens = sum(len((message.content or "").split()) for message in messages)
        has_tool_result = any(message.role == "tool" for message in messages)
        if self.case.expect_workflow_child_run and tools and not has_tool_result and not self._called_tool:
            self._called_tool = True
            return ChatResponse(
                text=None,
                tokens_prompt=prompt_tokens,
                tokens_completion=1,
                model=model,
                finish_reason="tool_calls",
                tool_calls=[
                    ToolCall(
                        id=f"call_{self.case.case_id}_workflow",
                        name=self.workflow_ref,
                        arguments=dict(self.workflow_inputs),
                    )
                ],
            )

        text = (
            "Refund escalations require account verification before approval. "
            "A review ticket was created using the refund policy evidence."
            if self.case.expect_workflow_child_run
            else "The refund policy requires account verification before a refund escalation is approved."
        )
        return ChatResponse(
            text=text,
            tokens_prompt=prompt_tokens,
            tokens_completion=len(text.split()),
            model=model,
            finish_reason="stop",
        )

    async def embed(self, texts: list[str], model: str, **kwargs: Any) -> EmbeddingResponse:
        return EmbeddingResponse(embeddings=[[0.0, 0.0, 0.0] for _ in texts], tokens_used=len(texts), model=model)

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        selected = documents[: top_n or None]
        return RerankResponse(
            results=[{"index": index, "document": document, "score": 1.0} for index, document in enumerate(selected)],
            tokens_used=0,
            model=model,
        )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run support/ticket Enterprise MVP regression checks.")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="12345678")
    parser.add_argument("--name", default="Test User")
    parser.add_argument("--tenant-name", default="default")
    parser.add_argument("--workspace-name", default="default")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--json-output", default=None)
    return parser.parse_args()


def _unwrap(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, tuple):
        return row[0]
    try:
        return row[0]
    except Exception:
        return row


def _load_cases(path: Path) -> list[SupportTicketGoldenCase]:
    raw_cases = json.loads(path.read_text(encoding="utf-8"))
    return [SupportTicketGoldenCase(**item) for item in raw_cases]


def _citation_matches_source(citation: dict[str, Any], expected_source: str) -> bool:
    candidates = [
        citation.get("doc_key"),
        citation.get("source"),
        citation.get("source_name"),
        citation.get("title"),
        citation.get("source_uri"),
    ]
    return any(expected_source in str(candidate or "") for candidate in candidates)


def _cost_summary(detail) -> dict[str, Any]:
    usage_entries = [item for item in detail.costs if item.entry_type == "usage"]
    charge_entries = [item for item in detail.costs if item.entry_type == "charge"]
    total_amount = sum(float(item.amount or 0) for item in charge_entries)
    total_tokens = sum(int(item.total_tokens or 0) for item in usage_entries)
    return {
        "entries": len(detail.costs),
        "usage_entries": len(usage_entries),
        "charge_entries": len(charge_entries),
        "amount": round(total_amount, 8),
        "tokens": total_tokens,
    }


def _required_governance_keys(case: SupportTicketGoldenCase) -> tuple[str, ...]:
    base_keys = (
        "actor_scope",
        "subject_version",
        "trace_timeline",
        "knowledge_citation",
        "cost_attribution",
        "replay_ready",
    )
    if not case.expect_workflow_child_run:
        return base_keys
    return (
        *base_keys,
        "tool_call",
        "child_workflow",
        "audit_record",
        "secret_boundary",
        "egress_policy",
    )


def _governance_failures(case: SupportTicketGoldenCase, governance_evidence: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    by_key = {item.get("key"): item for item in governance_evidence}
    for key in _required_governance_keys(case):
        item = by_key.get(key)
        if item is None:
            failures.append(f"missing governance evidence: {key}")
            continue
        status = item.get("status")
        if status != "pass":
            missing = item.get("missing") or []
            suffix = f" missing={missing}" if missing else ""
            failures.append(f"governance evidence failed: {key} status={status}{suffix}")
    return failures


def _case_pass_fail(case: SupportTicketGoldenCase, report: SupportTicketCaseReport) -> list[str]:
    failures: list[str] = []
    output_lc = report.output.lower()
    for term in case.minimum_answer_terms:
        if term.lower() not in output_lc:
            failures.append(f"answer missing term: {term}")
    if report.citation_count < 1:
        failures.append("missing citation")
    if case.expect_tool_call and report.tool_call_count < 1:
        failures.append("missing tool call")
    if not case.expect_tool_call and report.tool_call_count != 0:
        failures.append("unexpected tool call")
    if case.expect_workflow_child_run and report.child_run_count < 1:
        failures.append("missing workflow child run")
    if not case.expect_workflow_child_run and report.child_run_count != 0:
        failures.append("unexpected workflow child run")
    if case.expect_audit and report.audit_count < 1:
        failures.append("missing audit evidence")
    if not case.expect_audit and report.audit_count != 0:
        failures.append("unexpected audit evidence")
    return failures


def _workflow_inputs(db, bootstrap: BootstrapResult) -> dict[str, Any]:
    index = _unwrap(
        db.exec(
            select(KnowledgeIndex).where(
                and_(
                    KnowledgeIndex.tenant_id == bootstrap.tenant_id,
                    KnowledgeIndex.workspace_id == bootstrap.workspace_id,
                    KnowledgeIndex.knowledge_id == bootstrap.knowledge_id,
                    KnowledgeIndex.is_primary.is_(True),
                )
            )
        ).first()
    )
    collection_name = index.collection_name if index else f"kb_{bootstrap.knowledge_id}"
    return {
        "customer_message": "Customer customer-123 requests a refund escalation.",
        "customer_id": "customer-123",
        "priority": "high",
        "knowledge_collection": collection_name,
        "embedding_model": "model:test:embedding",
        "model_ref": "model:test:workflow",
    }


def register_preapproved_evaluation_tool(ctx: RequestContext) -> None:
    """Keep the deterministic evidence run non-interactive without changing production policy."""

    router = RegistryToolRouterPort()
    if not router.register_builtin(DEMO_TICKET_TOOL_REF, ctx):
        raise RuntimeError("Support evaluation ticket tool is unavailable")
    registry = get_registry()
    registered = registry.get_latest(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=DEMO_TICKET_TOOL_REF,
    )
    if registered is None:
        raise RuntimeError("Support evaluation ticket ToolSpec was not registered")
    _, payload = registered
    evaluation_payload = copy.deepcopy(payload)
    policy = evaluation_payload["tool_spec"].setdefault("policy", {})
    policy["approval"] = {
        "mode": "none",
        "reason": "deterministic_evaluation_preapproval",
    }
    registry.register(
        kind="tool",
        tenant_id=ctx.tenant_id,
        workspace_id=ctx.workspace_id,
        name=DEMO_TICKET_TOOL_REF,
        version="1.0.1",
        payload=evaluation_payload,
    )


async def _run_case(db, ctx: RequestContext, bootstrap: BootstrapResult, case: SupportTicketGoldenCase) -> SupportTicketCaseReport:
    reset_container()
    start = time.perf_counter()
    workflow_ref = f"wf:{bootstrap.workflow_id}"
    service = AgentApplicationService(
        db=db,
        ctx=ctx,
        llm_port=SupportTicketEvaluationLLMPort(
            case,
            workflow_ref=workflow_ref,
            workflow_inputs=_workflow_inputs(db, bootstrap),
        ),
        tool_port=RegistryToolRouterPort(),
        response_service=build_response_service(db=db, ctx=ctx),
    )
    result = await service.execute_agent(
        bootstrap.agent_id,
        AgentRunRequest(
            input=case.prompt,
        ).model_dump(exclude_none=True),
    )
    latency_ms = max(0, int((time.perf_counter() - start) * 1000))
    detail = RunService(db=db, ctx=ctx).get_run(result["run_id"])
    citations = [item for item in detail.citations if isinstance(item, dict)]
    governance_evidence = [item.model_dump() for item in detail.governance_evidence]
    governance_failures = _governance_failures(case, governance_evidence)
    failure_reasons: list[str] = []
    if not any(_citation_matches_source(item, case.expected_citation_source) for item in citations):
        failure_reasons.append(f"missing expected citation source: {case.expected_citation_source}")

    report = SupportTicketCaseReport(
        case_id=case.case_id,
        passed=False,
        failure_reasons=[],
        prompt=case.prompt,
        output=str(result.get("output") or ""),
        run_id=result.get("run_id"),
        response_id=result.get("response_id"),
        thread_id=result.get("thread_id"),
        expected_citation_source=case.expected_citation_source,
        tool_call_count=len(detail.tool_calls),
        citation_count=len(citations),
        audit_count=len(detail.audits),
        child_run_count=len(detail.child_runs),
        latency_ms=latency_ms,
        cost=_cost_summary(detail),
        run_explorer_url=f"/observe/runs/{result['run_id']}" if result.get("run_id") else None,
        governance_evidence=governance_evidence,
        governance_passed=not governance_failures,
        governance_failures=governance_failures,
    )
    failure_reasons.extend(_case_pass_fail(case, report))
    failure_reasons.extend(governance_failures)
    report.failure_reasons = failure_reasons
    report.passed = not failure_reasons
    return report


async def evaluate_support_ticket_regression(db, args: argparse.Namespace) -> dict[str, Any]:
    bootstrap = await bootstrap_enterprise_mvp(db, args)
    ctx = RequestContext(
        tenant_id=bootstrap.tenant_id,
        workspace_id=bootstrap.workspace_id,
        user_id=bootstrap.user_id,
        tenant_role="Owner",
        workspace_role="Owner",
    )
    register_preapproved_evaluation_tool(ctx)
    knowledge_service = build_knowledge_runtime_service(db=db, ctx=ctx)
    original_knowledge_query = knowledge_tools.knowledge_query

    async def query_local_knowledge(**kwargs: Any) -> dict[str, Any]:
        response = await knowledge_service.query(
            kwargs["knowledge_id"],
            QueryRequest(
                query=kwargs["query"],
                top_k=kwargs.get("top_k", 5),
                index_id=kwargs.get("index_id"),
                filter=kwargs.get("filter"),
                include_snippets=kwargs.get("include_snippets", True),
                strategy=kwargs.get("strategy"),
            ),
        )
        return response.model_dump()

    knowledge_tools.knowledge_query = query_local_knowledge
    try:
        case_reports = [
            await _run_case(db, ctx, bootstrap, case)
            for case in _load_cases(Path(args.cases_path))
        ]
    finally:
        knowledge_tools.knowledge_query = original_knowledge_query
    passed = sum(1 for case in case_reports if case.passed)
    report = {
        "scenario": "support_ticket",
        "passed": passed == len(case_reports),
        "tenant_id": bootstrap.tenant_id,
        "workspace_id": bootstrap.workspace_id,
        "agent_id": bootstrap.agent_id,
        "knowledge_id": bootstrap.knowledge_id,
        "workflow_id": bootstrap.workflow_id,
        "summary": {
            "total": len(case_reports),
            "passed": passed,
            "failed": len(case_reports) - passed,
        },
        "cases": [asdict(case) for case in case_reports],
    }
    if args.json_output:
        output_path = Path(args.json_output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    args = _parse_args()
    db = get_db_sync()
    try:
        report = asyncio.run(evaluate_support_ticket_regression(db, args))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
