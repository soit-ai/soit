import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, case, desc, func, select

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.responses import Response, ResponseEvent
from app.kernel.runtime.db.models.runs import Run, RunArtifact, RunCostEntry, RunStep
from app.kernel.runtime.responses.schemas import ResponseEventRead, ToolCallRead
from app.kernel.runtime.runs.protocols import RunQueryRepositoryProtocol
from app.kernel.runtime.runs.schemas import (
    RunArtifactResponse,
    RunAuditLogResponse,
    RunCostByModelResponse,
    RunCostByModeResponse,
    RunCostByProviderResponse,
    RunCostBySubjectResponse,
    RunCostDailyResponse,
    RunCostEntryResponse,
    RunCostSummaryResponse,
    RunDetailResponse,
    RunGovernanceEvidenceResponse,
    RunObserveSummaryResponse,
    RunResponse,
    RunStepMetricsSummaryResponse,
    RunStepResponse,
)


class RunService:
    """Run query service for run records and cost summaries."""

    def __init__(self, db: RunQueryRepositoryProtocol, ctx: RequestContext):
        self.db = db
        self.ctx = ctx

    @staticmethod
    def _unwrap_row(row: Any) -> Any:
        if row is None:
            return None
        if hasattr(row, "id"):
            return row
        try:
            return row[0]
        except Exception:
            return row

    def _list_responses_for_run(self, run_id: str) -> list[Response]:
        query = (
            select(Response)
            .where(
                and_(
                    Response.run_id == run_id,
                    Response.tenant_id == self.ctx.tenant_id,
                    Response.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(Response.created_at.asc(), Response.id.asc())
        )
        return [self._unwrap_row(row) for row in list(self.db.exec(query).all())]

    def _list_response_events_for_run(self, run_id: str) -> list[ResponseEventRead]:
        query = (
            select(ResponseEvent)
            .where(
                and_(
                    ResponseEvent.run_id == run_id,
                    ResponseEvent.tenant_id == self.ctx.tenant_id,
                    ResponseEvent.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(ResponseEvent.created_at.asc(), ResponseEvent.sequence.asc(), ResponseEvent.id.asc())
        )
        return [
            ResponseEventRead.model_validate(self._unwrap_row(row))
            for row in list(self.db.exec(query).all())
        ]

    def _project_tool_calls_for_run(
        self,
        *,
        run_id: str,
        steps: list[RunStepResponse],
        response_id: str | None,
    ) -> list[ToolCallRead]:
        projections: list[ToolCallRead] = []
        resolved_response_id = response_id or run_id
        for step in steps:
            tool_call = (
                (step.metrics_json or {}).get("tool_call")
                if isinstance(step.metrics_json, dict)
                else None
            ) or {}
            if not tool_call and step.step_type != "tool":
                continue
            tool_name = tool_call.get("tool_name") or tool_call.get("tool_ref")
            if not tool_name:
                continue
            projections.append(
                ToolCallRead(
                    id=step.id,
                    tenant_id=self.ctx.tenant_id,
                    workspace_id=self.ctx.workspace_id,
                    response_id=resolved_response_id,
                    run_id=run_id,
                    step_id=step.id,
                    thread_id=None,
                    task_id=None,
                    agent_id=None,
                    tool_name=tool_name,
                    tool_type=tool_call.get("tool_type", "builtin"),
                    status=tool_call.get("status") or step.status,
                    arguments_json=tool_call.get("arguments") or {},
                    result_json=tool_call.get("result") or {},
                    metadata_json=tool_call.get("metadata") or {},
                    error_code=tool_call.get("error_code") or step.error_code,
                    error_message=tool_call.get("error_message") or step.error_message,
                    started_at=step.started_at,
                    completed_at=step.ended_at,
                    created_at=step.created_at,
                    updated_at=step.ended_at or step.created_at,
                )
            )
        return projections

    @staticmethod
    def _response_citations(responses: list[Response]) -> list[dict[str, Any]]:
        citations: list[dict[str, Any]] = []
        for response in responses:
            response_citations = (response.output_json or {}).get("citations")
            if isinstance(response_citations, list):
                citations.extend([item for item in response_citations if isinstance(item, dict)])
        return citations

    @staticmethod
    def _step_has_audit(step: RunStep) -> bool:
        metrics = step.metrics_json if isinstance(step.metrics_json, dict) else {}
        return bool(metrics.get("audit_json") or metrics.get("audit_preview") or metrics.get("audit_artifact"))

    @staticmethod
    def _extract_child_run_ids_from_step_metrics(metrics: dict[str, Any] | None) -> list[str]:
        if not isinstance(metrics, dict):
            return []
        tool_call = metrics.get("tool_call") if isinstance(metrics.get("tool_call"), dict) else {}
        candidates: list[Any] = []
        if isinstance(tool_call, dict):
            result_payload = tool_call.get("result")
            metadata_payload = tool_call.get("metadata")
            if isinstance(result_payload, dict):
                candidates.append(result_payload.get("workflow_run_id"))
                nested = result_payload.get("result")
                if isinstance(nested, dict):
                    candidates.append(nested.get("workflow_run_id"))
            if isinstance(metadata_payload, dict):
                candidates.append(metadata_payload.get("workflow_run_id"))
        seen: set[str] = set()
        child_run_ids: list[str] = []
        for candidate in candidates:
            if isinstance(candidate, str) and candidate and candidate not in seen:
                seen.add(candidate)
                child_run_ids.append(candidate)
        return child_run_ids

    def build_observe_summaries(self, run_ids: list[str]) -> dict[str, RunObserveSummaryResponse]:
        """Build lightweight observability summaries for the given runs."""
        unique_run_ids = list(dict.fromkeys(run_ids))
        summaries = {run_id: RunObserveSummaryResponse() for run_id in unique_run_ids}
        if not unique_run_ids:
            return summaries

        steps_query = select(RunStep).where(
            and_(
                RunStep.run_id.in_(unique_run_ids),
                RunStep.tenant_id == self.ctx.tenant_id,
                RunStep.workspace_id == self.ctx.workspace_id,
            )
        )
        steps = [self._unwrap_row(row) for row in list(self.db.exec(steps_query).all())]
        child_run_ids_by_run: dict[str, set[str]] = {run_id: set() for run_id in unique_run_ids}
        for step in steps:
            summary = summaries.get(step.run_id)
            if not summary:
                continue
            summary.step_count += 1
            if step.step_type == "tool":
                summary.tool_call_count += 1
            if self._step_has_audit(step):
                summary.audit_count += 1
            for child_run_id in self._extract_child_run_ids_from_step_metrics(step.metrics_json):
                child_run_ids_by_run.setdefault(step.run_id, set()).add(child_run_id)

        responses_query = select(Response).where(
            and_(
                Response.run_id.in_(unique_run_ids),
                Response.tenant_id == self.ctx.tenant_id,
                Response.workspace_id == self.ctx.workspace_id,
            )
        )
        responses = [self._unwrap_row(row) for row in list(self.db.exec(responses_query).all())]
        for response in responses:
            summary = summaries.get(response.run_id)
            if not summary:
                continue
            citations = (response.output_json or {}).get("citations") if isinstance(response.output_json, dict) else None
            if isinstance(citations, list):
                summary.citation_count += sum(1 for item in citations if isinstance(item, dict))

        response_events_query = select(ResponseEvent).where(
            and_(
                ResponseEvent.run_id.in_(unique_run_ids),
                ResponseEvent.tenant_id == self.ctx.tenant_id,
                ResponseEvent.workspace_id == self.ctx.workspace_id,
            )
        )
        response_events = [self._unwrap_row(row) for row in list(self.db.exec(response_events_query).all())]
        for event in response_events:
            summary = summaries.get(event.run_id)
            if summary:
                summary.response_event_count += 1

        costs_query = select(RunCostEntry).where(
            and_(
                RunCostEntry.run_id.in_(unique_run_ids),
                RunCostEntry.tenant_id == self.ctx.tenant_id,
                RunCostEntry.workspace_id == self.ctx.workspace_id,
            )
        )
        costs = [self._unwrap_row(row) for row in list(self.db.exec(costs_query).all())]
        for cost in costs:
            summary = summaries.get(cost.run_id)
            if summary:
                summary.cost_entry_count += 1

        for run_id, child_run_ids in child_run_ids_by_run.items():
            summaries[run_id].child_run_count = len(child_run_ids)

        return summaries

    @staticmethod
    def _extract_child_run_ids(tool_calls: list[ToolCallRead]) -> list[str]:
        seen: set[str] = set()
        child_run_ids: list[str] = []
        for tool_call in tool_calls:
            candidates: list[Any] = []
            result_payload = tool_call.result_json or {}
            if isinstance(result_payload, dict):
                candidates.append(result_payload.get("workflow_run_id"))
                nested = result_payload.get("result")
                if isinstance(nested, dict):
                    candidates.append(nested.get("workflow_run_id"))
            metadata_payload = tool_call.metadata_json or {}
            if isinstance(metadata_payload, dict):
                candidates.append(metadata_payload.get("workflow_run_id"))
            for candidate in candidates:
                if isinstance(candidate, str) and candidate and candidate not in seen:
                    seen.add(candidate)
                    child_run_ids.append(candidate)
        return child_run_ids

    def _list_child_runs(self, child_run_ids: list[str]) -> list[RunResponse]:
        if not child_run_ids:
            return []
        query = (
            select(Run)
            .where(
                and_(
                    Run.id.in_(child_run_ids),
                    Run.tenant_id == self.ctx.tenant_id,
                    Run.workspace_id == self.ctx.workspace_id,
                )
            )
            .order_by(Run.started_at.asc(), Run.id.asc())
        )
        return [
            RunResponse.model_validate(self._unwrap_row(row))
            for row in list(self.db.exec(query).all())
        ]

    @staticmethod
    def _flatten_strings(value: Any) -> list[str]:
        results: list[str] = []
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            for key, item in value.items():
                results.append(str(key))
                results.extend(RunService._flatten_strings(item))
        elif isinstance(value, list):
            for item in value:
                results.extend(RunService._flatten_strings(item))
        return results

    @staticmethod
    def _payload_has_key(value: Any, keys: set[str]) -> bool:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in keys:
                    return True
                if RunService._payload_has_key(item, keys):
                    return True
        elif isinstance(value, list):
            return any(RunService._payload_has_key(item, keys) for item in value)
        return False

    @staticmethod
    def _payload_values_for_keys(value: Any, keys: set[str]) -> list[Any]:
        values: list[Any] = []
        if isinstance(value, dict):
            for key, item in value.items():
                if key in keys:
                    values.append(item)
                values.extend(RunService._payload_values_for_keys(item, keys))
        elif isinstance(value, list):
            for item in value:
                values.extend(RunService._payload_values_for_keys(item, keys))
        return values

    @staticmethod
    def _url_refs(value: Any) -> list[str]:
        return [
            item
            for item in RunService._flatten_strings(value)
            if item.startswith(("http://", "https://"))
        ]

    @staticmethod
    def _evidence(
        key: str,
        *,
        status: str,
        label: str,
        summary: str,
        evidence_refs: list[str] | None = None,
        missing: list[str] | None = None,
    ) -> RunGovernanceEvidenceResponse:
        return RunGovernanceEvidenceResponse(
            key=key,
            status=status,
            label=label,
            summary=summary,
            evidence_refs=list(dict.fromkeys(evidence_refs or [])),
            missing=missing or [],
        )

    def _build_governance_evidence(
        self,
        *,
        run: Run,
        steps: list[RunStepResponse],
        cost_entries: list[RunCostEntryResponse],
        response_events: list[ResponseEventRead],
        tool_calls: list[ToolCallRead],
        citations: list[dict[str, Any]],
        audits: list[RunAuditLogResponse],
        child_runs: list[RunResponse],
    ) -> list[RunGovernanceEvidenceResponse]:
        step_metrics = [step.metrics_json or {} for step in steps if isinstance(step.metrics_json, dict)]
        audit_payloads: list[Any] = []
        for audit in audits:
            audit_payloads.extend([audit.request, audit.response, audit.preview])

        actor_missing = [
            field
            for field, value in {
                "tenant_id": run.tenant_id,
                "workspace_id": run.workspace_id,
                "user_id": run.user_id,
                "run_id": run.id,
            }.items()
            if not value
        ]
        subject_missing = [
            field
            for field, value in {
                "subject_kind": run.subject_kind,
                "subject_id": run.subject_id,
                "subject_version_id": run.subject_version_id,
            }.items()
            if not value
        ]
        capability_refs = [
            str(value)
            for metrics in step_metrics
            for value in self._payload_values_for_keys(metrics, {"capability_binding", "bindings", "tool_refs", "workflow_refs", "knowledge_refs", "model_ref"})
        ]
        permission_refs = [
            str(value)
            for metrics in step_metrics
            for value in self._payload_values_for_keys(metrics, {"permission_scope", "rbac", "resource_grant", "policy_decision"})
        ]
        secret_refs = [
            value
            for payload in [*step_metrics, *audit_payloads]
            for value in self._flatten_strings(payload)
            if value.startswith("secret:")
        ]
        has_secret_key = any(
            self._payload_has_key(payload, {"secret_ref", "secret_refs", "credential_ref"})
            for payload in [*step_metrics, *audit_payloads]
        )
        leaked_secret = any(
            ("sk-" in value or "Bearer " in value)
            and not value.startswith("secret:")
            for payload in audit_payloads
            for value in self._flatten_strings(payload)
        )
        egress_refs = [
            str(value)
            for payload in [*step_metrics, *audit_payloads]
            for value in self._payload_values_for_keys(payload, {"egress", "egress_policy", "decision", "egress_decision"})
        ]
        url_refs = [
            value
            for payload in [*step_metrics, *audit_payloads]
            for value in self._url_refs(payload)
        ]
        has_egress_key = any(
            self._payload_has_key(payload, {"egress", "egress_policy", "egress_decision"})
            for payload in [*step_metrics, *audit_payloads]
        )
        has_egress_evidence = bool(egress_refs or has_egress_key or url_refs)

        replay_missing: list[str] = []
        if not steps:
            replay_missing.append("steps")
        if not response_events:
            replay_missing.append("response_events")
        if not cost_entries:
            replay_missing.append("costs")
        if not citations:
            replay_missing.append("citations")
        if tool_calls and not audits:
            replay_missing.append("audits")

        return [
            self._evidence(
                "actor_scope",
                status="fail" if actor_missing else "pass",
                label="Actor and scope",
                summary="Run is tied to tenant, workspace, user, and run identifiers." if not actor_missing else "Run scope is incomplete.",
                evidence_refs=[value for value in [run.tenant_id, run.workspace_id, run.user_id, run.id] if value],
                missing=actor_missing,
            ),
            self._evidence(
                "subject_version",
                status="fail" if subject_missing else "pass",
                label="Subject version",
                summary="Run is tied to a versioned subject." if not subject_missing else "Run is missing versioned subject fields.",
                evidence_refs=[value for value in [run.subject_kind, run.subject_id, run.subject_version_id] if value],
                missing=subject_missing,
            ),
            self._evidence(
                "capability_binding",
                status="pass" if capability_refs else "warning",
                label="Capability binding",
                summary="Published capability binding evidence was recorded." if capability_refs else "No explicit capability binding evidence was recorded on run steps.",
                evidence_refs=capability_refs,
                missing=[] if capability_refs else ["capability_binding"],
            ),
            self._evidence(
                "permission_scope",
                status="pass" if permission_refs else "warning",
                label="Permission scope",
                summary="Permission or policy decision evidence was recorded." if permission_refs else "No explicit permission decision evidence was recorded on run steps.",
                evidence_refs=permission_refs,
                missing=[] if permission_refs else ["permission_scope"],
            ),
            self._evidence(
                "secret_boundary",
                status="fail" if leaked_secret else ("pass" if secret_refs or has_secret_key else "warning"),
                label="Secret boundary",
                summary=(
                    "Secret references are present and audit payloads do not expose obvious plaintext secrets."
                    if secret_refs or has_secret_key
                    else "No secret reference evidence was recorded for this run."
                ),
                evidence_refs=secret_refs,
                missing=(["redaction"] if leaked_secret else ([] if secret_refs or has_secret_key else ["secret_ref"])),
            ),
            self._evidence(
                "egress_policy",
                status="pass" if has_egress_evidence else "warning",
                label="Egress policy",
                summary="Egress decision evidence was recorded." if has_egress_evidence else "No egress decision evidence was recorded for this run.",
                evidence_refs=[*egress_refs, *url_refs],
                missing=[] if has_egress_evidence else ["egress_decision"],
            ),
            self._evidence(
                "audit_record",
                status="pass" if audits else "fail",
                label="Audit record",
                summary=f"{len(audits)} audit record(s) are attached." if audits else "No gateway audit records are attached.",
                evidence_refs=[f"{audit.run_id}:{audit.step_id}" for audit in audits],
                missing=[] if audits else ["audits"],
            ),
            self._evidence(
                "cost_attribution",
                status="pass" if cost_entries else "fail",
                label="Cost attribution",
                summary=f"{len(cost_entries)} cost entry(s) are attached." if cost_entries else "No cost entries are attached.",
                evidence_refs=[cost.id for cost in cost_entries],
                missing=[] if cost_entries else ["costs"],
            ),
            self._evidence(
                "trace_timeline",
                status="pass" if steps or response_events else "fail",
                label="Trace timeline",
                summary=f"{len(steps)} step(s), {len(response_events)} response event(s)." if steps or response_events else "No run steps or response events are attached.",
                evidence_refs=[*[step.id for step in steps], *[event.id for event in response_events]],
                missing=[] if steps or response_events else ["steps", "response_events"],
            ),
            self._evidence(
                "tool_call",
                status="pass" if tool_calls else "not_applicable",
                label="Tool call",
                summary=f"{len(tool_calls)} tool call(s) are attached." if tool_calls else "No tool calls were recorded for this run.",
                evidence_refs=[tool_call.id for tool_call in tool_calls],
            ),
            self._evidence(
                "knowledge_citation",
                status="pass" if citations else "fail",
                label="Knowledge citation",
                summary=f"{len(citations)} citation(s) are attached." if citations else "No knowledge citations are attached.",
                evidence_refs=[
                    str(citation.get("chunk_id") or citation.get("document_id") or citation.get("knowledge_id") or index)
                    for index, citation in enumerate(citations)
                ],
                missing=[] if citations else ["citations"],
            ),
            self._evidence(
                "child_workflow",
                status="pass" if child_runs else "not_applicable",
                label="Child workflow",
                summary=f"{len(child_runs)} child workflow run(s) are attached." if child_runs else "No child workflow runs were recorded for this run.",
                evidence_refs=[child_run.id for child_run in child_runs],
            ),
            self._evidence(
                "replay_ready",
                status="fail" if replay_missing else "pass",
                label="Replay ready",
                summary="Run detail has enough evidence for operator replay." if not replay_missing else "Run detail is missing replay evidence.",
                evidence_refs=[run.id],
                missing=replay_missing,
            ),
        ]

    def _run_ids_for_tool_calls(self) -> set[str]:
        query = select(RunStep).where(
            and_(
                RunStep.tenant_id == self.ctx.tenant_id,
                RunStep.workspace_id == self.ctx.workspace_id,
                RunStep.step_type == "tool",
            )
        )
        return {self._unwrap_row(row).run_id for row in list(self.db.exec(query).all())}

    def _run_ids_for_citations(self) -> set[str]:
        query = select(Response).where(
            and_(
                Response.tenant_id == self.ctx.tenant_id,
                Response.workspace_id == self.ctx.workspace_id,
            )
        )
        run_ids: set[str] = set()
        for row in list(self.db.exec(query).all()):
            response = self._unwrap_row(row)
            citations = (response.output_json or {}).get("citations") if isinstance(response.output_json, dict) else None
            if isinstance(citations, list) and any(isinstance(item, dict) for item in citations):
                run_ids.add(response.run_id)
        return run_ids

    def _run_ids_for_audits(self) -> set[str]:
        query = select(RunStep).where(
            and_(
                RunStep.tenant_id == self.ctx.tenant_id,
                RunStep.workspace_id == self.ctx.workspace_id,
            )
        )
        run_ids: set[str] = set()
        for row in list(self.db.exec(query).all()):
            step = self._unwrap_row(row)
            if self._step_has_audit(step):
                run_ids.add(step.run_id)
        return run_ids

    def _run_ids_matching_observe_filters(
        self,
        *,
        has_tool_call: bool | None = None,
        has_citation: bool | None = None,
        has_audit: bool | None = None,
    ) -> set[str] | None:
        required_sets: list[set[str]] = []
        if has_tool_call:
            required_sets.append(self._run_ids_for_tool_calls())
        if has_citation:
            required_sets.append(self._run_ids_for_citations())
        if has_audit:
            required_sets.append(self._run_ids_for_audits())
        if not required_sets:
            return None
        result = required_sets[0]
        for item in required_sets[1:]:
            result = result.intersection(item)
        return result

    def list_runs(
        self,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        trace_id: str | None = None,
        user_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        include_observe_summary: bool = False,
        has_tool_call: bool | None = None,
        has_citation: bool | None = None,
        has_audit: bool | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RunResponse]:
        """List runs with optional filters."""
        clauses = [
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if trace_id:
            clauses.append(Run.trace_id == trace_id)
        if user_id:
            clauses.append(Run.user_id == user_id)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)
        observe_run_ids = self._run_ids_matching_observe_filters(
            has_tool_call=has_tool_call,
            has_citation=has_citation,
            has_audit=has_audit,
        )
        if observe_run_ids is not None:
            if not observe_run_ids:
                return []
            clauses.append(Run.id.in_(list(observe_run_ids)))

        query = (
            select(Run)
            .where(and_(*clauses))
            .order_by(desc(Run.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        runs = []
        for item in rows:
            if hasattr(item, "id"):
                runs.append(item)
            else:
                try:
                    runs.append(item[0])
                except Exception:
                    continue
        responses = [RunResponse.model_validate(run) for run in runs]
        if include_observe_summary and responses:
            summaries = self.build_observe_summaries([run.id for run in responses])
            responses = [
                run.model_copy(update={"observe_summary": summaries.get(run.id, RunObserveSummaryResponse())})
                for run in responses
            ]
        return responses

    def _build_step_clauses(
        self,
        *,
        run_id: str | None = None,
        trace_id: str | None = None,
        step_id: str | None = None,
        step_type: str | None = None,
        status: str | None = None,
        node_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        ended_after: datetime | None = None,
        ended_before: datetime | None = None,
    ) -> list[Any]:
        clauses: list[Any] = [
            RunStep.tenant_id == self.ctx.tenant_id,
            RunStep.workspace_id == self.ctx.workspace_id,
        ]
        if run_id:
            clauses.append(RunStep.run_id == run_id)
        if trace_id:
            clauses.append(RunStep.trace_id == trace_id)
        if step_id:
            clauses.append(RunStep.step_id == step_id)
        if step_type:
            clauses.append(RunStep.step_type == step_type)
        if status:
            clauses.append(RunStep.status == status)
        if node_id:
            clauses.append(RunStep.node_id == node_id)
        if started_after:
            clauses.append(RunStep.started_at >= started_after)
        if started_before:
            clauses.append(RunStep.started_at <= started_before)
        if ended_after:
            clauses.append(RunStep.ended_at >= ended_after)
        if ended_before:
            clauses.append(RunStep.ended_at <= ended_before)
        return clauses

    def list_steps(
        self,
        *,
        run_id: str | None = None,
        trace_id: str | None = None,
        step_id: str | None = None,
        step_type: str | None = None,
        status: str | None = None,
        node_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        ended_after: datetime | None = None,
        ended_before: datetime | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[RunStepResponse]:
        """List run steps with optional filters."""
        clauses = self._build_step_clauses(
            run_id=run_id,
            trace_id=trace_id,
            step_id=step_id,
            step_type=step_type,
            status=status,
            node_id=node_id,
            started_after=started_after,
            started_before=started_before,
            ended_after=ended_after,
            ended_before=ended_before,
        )
        query = (
            select(RunStep)
            .where(and_(*clauses))
            .order_by(desc(RunStep.created_at))
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.exec(query).all())
        steps = []
        for item in rows:
            if hasattr(item, "id"):
                steps.append(item)
            else:
                try:
                    steps.append(item[0])
                except Exception:
                    continue
        return [RunStepResponse.model_validate(step) for step in steps]

    def summarize_step_metrics(
        self,
        *,
        run_id: str | None = None,
        trace_id: str | None = None,
        step_id: str | None = None,
        step_type: str | None = None,
        status: str | None = None,
        node_id: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        ended_after: datetime | None = None,
        ended_before: datetime | None = None,
    ) -> list[RunStepMetricsSummaryResponse]:
        """Aggregate step metrics by step_type and status."""
        clauses = self._build_step_clauses(
            run_id=run_id,
            trace_id=trace_id,
            step_id=step_id,
            step_type=step_type,
            status=status,
            node_id=node_id,
            started_after=started_after,
            started_before=started_before,
            ended_after=ended_after,
            ended_before=ended_before,
        )
        query = select(RunStep).where(and_(*clauses))
        rows = list(self.db.exec(query).all())
        steps = [row if hasattr(row, "id") else row[0] for row in rows]

        summary: dict[tuple[str, str], dict[str, Any]] = {}
        for step in steps:
            key = (step.step_type, step.status)
            bucket = summary.setdefault(
                key,
                {
                    "count": 0,
                    "latency_total": 0.0,
                    "latency_count": 0,
                    "latency_min": None,
                    "latency_max": None,
                },
            )
            bucket["count"] += 1

            latency_ms = None
            metrics = step.metrics_json or {}
            if isinstance(metrics, dict) and "latency_ms" in metrics:
                latency_ms = metrics.get("latency_ms")
            if latency_ms is None and step.started_at and step.ended_at:
                delta = step.ended_at - step.started_at
                latency_ms = int(delta.total_seconds() * 1000)

            try:
                latency_val = float(latency_ms) if latency_ms is not None else None
            except (TypeError, ValueError):
                latency_val = None

            if latency_val is not None:
                bucket["latency_total"] += latency_val
                bucket["latency_count"] += 1
                bucket["latency_min"] = (
                    latency_val if bucket["latency_min"] is None else min(bucket["latency_min"], latency_val)
                )
                bucket["latency_max"] = (
                    latency_val if bucket["latency_max"] is None else max(bucket["latency_max"], latency_val)
                )

        results: list[RunStepMetricsSummaryResponse] = []
        for (step_type_val, status_val), bucket in sorted(summary.items()):
            avg_latency = None
            if bucket["latency_count"]:
                avg_latency = bucket["latency_total"] / bucket["latency_count"]
            results.append(
                RunStepMetricsSummaryResponse(
                    step_type=step_type_val,
                    status=status_val,
                    count=bucket["count"],
                    avg_latency_ms=avg_latency,
                    min_latency_ms=(
                        int(bucket["latency_min"]) if bucket["latency_min"] is not None else None
                    ),
                    max_latency_ms=(
                        int(bucket["latency_max"]) if bucket["latency_max"] is not None else None
                    ),
                )
            )
        return results

    def get_run(
        self,
        run_id: str,
        *,
        include_steps: bool = True,
        include_artifacts: bool = True,
        include_cost: bool = True,
    ) -> RunDetailResponse:
        """Get run details."""
        query = select(Run).where(
            and_(
                Run.id == run_id,
                Run.tenant_id == self.ctx.tenant_id,
                Run.workspace_id == self.ctx.workspace_id,
            )
        )
        run = self.db.exec(query).first()
        if run and not hasattr(run, "id"):
            try:
                run = run[0]
            except Exception:
                run = None
        if not run:
            raise NotFoundError(f"Run not found: {run_id}")

        steps: list[RunStepResponse] = []
        artifacts: list[RunArtifactResponse] = []
        cost_summary: RunCostSummaryResponse | None = None
        cost_entries: list[RunCostEntryResponse] = []

        if include_steps:
            steps_query = select(RunStep).where(
                and_(
                    RunStep.run_id == run_id,
                    RunStep.tenant_id == self.ctx.tenant_id,
                    RunStep.workspace_id == self.ctx.workspace_id,
                )
            ).order_by(RunStep.created_at)
            raw_steps = list(self.db.exec(steps_query).all())
            steps = [
                RunStepResponse.model_validate(item if hasattr(item, "id") else item[0])
                for item in raw_steps
            ]

        if include_artifacts:
            artifacts_query = select(RunArtifact).where(
                and_(
                    RunArtifact.run_id == run_id,
                    RunArtifact.tenant_id == self.ctx.tenant_id,
                    RunArtifact.workspace_id == self.ctx.workspace_id,
                )
            ).order_by(RunArtifact.created_at)
            raw_artifacts = list(self.db.exec(artifacts_query).all())
            artifacts = [
                RunArtifactResponse.model_validate(item if hasattr(item, "id") else item[0])
                for item in raw_artifacts
            ]

        if include_cost:
            entries_query = select(RunCostEntry).where(
                and_(
                    RunCostEntry.run_id == run_id,
                    RunCostEntry.tenant_id == self.ctx.tenant_id,
                    RunCostEntry.workspace_id == self.ctx.workspace_id,
                )
            ).order_by(RunCostEntry.created_at)
            raw_entries = list(self.db.exec(entries_query).all())
            entries = [item if hasattr(item, "id") else item[0] for item in raw_entries]
            cost_entries = [RunCostEntryResponse.model_validate(item) for item in entries]
            cost_summary = self._summarize_entries(entries)

        responses = self._list_responses_for_run(run_id)
        response_events = self._list_response_events_for_run(run_id)
        tool_calls = self._project_tool_calls_for_run(
            run_id=run_id,
            steps=steps,
            response_id=responses[0].id if responses else None,
        )
        citations = self._response_citations(responses)
        child_run_ids = self._extract_child_run_ids(tool_calls)
        audits = self.list_audits(run_id=run_id, limit=200, offset=0)
        for child_run_id in child_run_ids:
            audits.extend(self.list_audits(run_id=child_run_id, limit=200, offset=0))
        child_runs = self._list_child_runs(child_run_ids)
        governance_evidence = self._build_governance_evidence(
            run=run,
            steps=steps,
            cost_entries=cost_entries,
            response_events=response_events,
            tool_calls=tool_calls,
            citations=citations,
            audits=audits,
            child_runs=child_runs,
        )

        return RunDetailResponse(
            run=RunResponse.model_validate(run),
            steps=steps,
            artifacts=artifacts,
            cost_summary=cost_summary,
            costs=cost_entries,
            response_events=response_events,
            tool_calls=tool_calls,
            citations=citations,
            audits=audits,
            child_runs=child_runs,
            governance_evidence=governance_evidence,
        )

    def list_audits(
        self,
        *,
        run_id: str | None = None,
        step_id: str | None = None,
        step_type: str | None = None,
        gateway_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RunAuditLogResponse]:
        """List audit logs derived from run steps."""
        requested_gateway_type = gateway_type
        clauses = [
            RunStep.tenant_id == self.ctx.tenant_id,
            RunStep.workspace_id == self.ctx.workspace_id,
        ]
        if run_id:
            clauses.append(RunStep.run_id == run_id)
        if step_id:
            clauses.append(RunStep.id == step_id)
        if step_type:
            clauses.append(RunStep.step_type == step_type)

        query = (
            select(RunStep)
            .where(and_(*clauses))
            .order_by(desc(RunStep.created_at))
        )
        if not gateway_type:
            query = query.offset(offset).limit(limit)
        rows = list(self.db.exec(query).all())
        steps = [row if hasattr(row, "id") else row[0] for row in rows]

        entries: list[RunAuditLogResponse] = []
        for step in steps:
            metrics = step.metrics_json or {}
            audit_json = metrics.get("audit_json")
            audit_preview = metrics.get("audit_preview")
            audit_artifact = metrics.get("audit_artifact")
            if not audit_json and not audit_preview and not audit_artifact:
                continue

            parsed = None
            if audit_json:
                try:
                    parsed = json.loads(audit_json)
                except Exception:
                    parsed = None

            gateway_type = None
            request_payload = None
            response_payload = None
            timestamp = None
            if isinstance(parsed, dict):
                gateway_type = parsed.get("gateway_type")
                request_payload = parsed.get("request")
                response_payload = parsed.get("response")
                timestamp = parsed.get("timestamp")
            if requested_gateway_type and requested_gateway_type != gateway_type:
                continue

            entries.append(
                RunAuditLogResponse(
                    run_id=step.run_id,
                    step_id=step.id,
                    step_type=step.step_type,
                    gateway_type=gateway_type,
                    request=request_payload,
                    response=response_payload,
                    timestamp=timestamp,
                    truncated=bool(metrics.get("audit_truncated")),
                    preview=audit_preview,
                    artifact_key=audit_artifact,
                )
            )

        if requested_gateway_type:
            return entries[offset : offset + limit]
        return entries

    def summarize_costs(
        self,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> RunCostSummaryResponse:
        """Aggregate cost metrics for runs."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = select(
            func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
            func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
            func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
        ).select_from(RunCostEntry).join(Run, RunCostEntry.run_id == Run.id).where(and_(*clauses))

        row = self.db.exec(query).one()
        return RunCostSummaryResponse(
            tokens_prompt=int(row[0] or 0),
            tokens_completion=int(row[1] or 0),
            embedding_count=int(row[2] or 0),
            rerank_count=int(row[3] or 0),
            ms_total=int(row[4] or 0),
            storage_bytes=int(row[5] or 0),
        )

    def summarize_costs_by_day(
        self,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostDailyResponse]:
        """Aggregate cost metrics per day."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        day_col = func.date(Run.started_at)
        query = (
            select(
                day_col.label("day"),
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(day_col)
            .order_by(day_col)
        )

        rows = list(self.db.exec(query).all())
        results: list[RunCostDailyResponse] = []
        for row in rows:
            day = row[0]
            results.append(
                RunCostDailyResponse(
                    date=str(day),
                    tokens_prompt=int(row[1] or 0),
                    tokens_completion=int(row[2] or 0),
                    embedding_count=int(row[3] or 0),
                    rerank_count=int(row[4] or 0),
                    ms_total=int(row[5] or 0),
                    storage_bytes=int(row[6] or 0),
                )
            )
        return results

    def summarize_costs_by_subject(
        self,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        subject_version_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostBySubjectResponse]:
        """Aggregate cost metrics per subject version."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = (
            select(
                Run.subject_version_id,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(Run.subject_version_id)
            .order_by(Run.subject_version_id)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostBySubjectResponse(
                subject_version_id=row[0],
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def summarize_costs_by_mode(
        self,
        *,
        mode: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        kind: str | None = None,
    ) -> list[RunCostByModeResponse]:
        """Aggregate cost metrics per run mode."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)
        if kind:
            clauses.append(Run.kind == kind)

        query = (
            select(
                Run.mode,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(Run.mode)
            .order_by(Run.mode)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostByModeResponse(
                mode=str(row[0]),
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def summarize_costs_by_provider(
        self,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostByProviderResponse]:
        """Aggregate cost metrics per provider."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = (
            select(
                RunCostEntry.provider,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(RunCostEntry.provider)
            .order_by(RunCostEntry.provider)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostByProviderResponse(
                provider=row[0],
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def summarize_costs_by_model(
        self,
        *,
        mode: str | None = None,
        kind: str | None = None,
        subject_version_id: str | None = None,
        subject_version_ids: list[str] | None = None,
        subject_kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
    ) -> list[RunCostByModelResponse]:
        """Aggregate cost metrics per model."""
        clauses = [
            RunCostEntry.tenant_id == self.ctx.tenant_id,
            RunCostEntry.workspace_id == self.ctx.workspace_id,
            RunCostEntry.run_id == Run.id,
            Run.tenant_id == self.ctx.tenant_id,
            Run.workspace_id == self.ctx.workspace_id,
        ]
        if mode:
            clauses.append(Run.mode == mode)
        if kind:
            clauses.append(Run.kind == kind)
        if subject_kind:
            clauses.append(Run.subject_kind == subject_kind)
        if subject_id:
            clauses.append(Run.subject_id == subject_id)
        if subject_version_id:
            clauses.append(Run.subject_version_id == subject_version_id)
        if subject_version_ids:
            clauses.append(Run.subject_version_id.in_(subject_version_ids))
        if status:
            clauses.append(Run.status == status)
        if started_after:
            clauses.append(Run.started_at >= started_after)
        if started_before:
            clauses.append(Run.started_at <= started_before)

        query = (
            select(
                RunCostEntry.model_ref,
                func.coalesce(func.sum(RunCostEntry.prompt_tokens), 0),
                func.coalesce(func.sum(RunCostEntry.completion_tokens), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit.in_(["embeddings", "embedding"]), RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "rerank", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "ms", RunCostEntry.quantity), else_=0)), 0),
                func.coalesce(func.sum(case((RunCostEntry.unit == "bytes", RunCostEntry.quantity), else_=0)), 0),
            )
            .select_from(RunCostEntry)
            .join(Run, RunCostEntry.run_id == Run.id)
            .where(and_(*clauses))
            .group_by(RunCostEntry.model_ref)
            .order_by(RunCostEntry.model_ref)
        )

        rows = list(self.db.exec(query).all())
        return [
            RunCostByModelResponse(
                model_ref=row[0],
                tokens_prompt=int(row[1] or 0),
                tokens_completion=int(row[2] or 0),
                embedding_count=int(row[3] or 0),
                rerank_count=int(row[4] or 0),
                ms_total=int(row[5] or 0),
                storage_bytes=int(row[6] or 0),
            )
            for row in rows
        ]

    def _summarize_entries(self, entries: list[RunCostEntry]) -> RunCostSummaryResponse:
        tokens_prompt = 0
        tokens_completion = 0
        embedding_count = 0
        rerank_count = 0
        ms_total = 0
        storage_bytes = 0

        for entry in entries:
            if entry.prompt_tokens:
                tokens_prompt += int(entry.prompt_tokens)
            if entry.completion_tokens:
                tokens_completion += int(entry.completion_tokens)
            if entry.unit in ("embeddings", "embedding"):
                embedding_count += int(entry.quantity)
            if entry.unit == "rerank":
                rerank_count += int(entry.quantity)
            if entry.unit == "ms":
                ms_total += int(entry.quantity)
            if entry.unit == "bytes":
                storage_bytes += int(entry.quantity)

        return RunCostSummaryResponse(
            tokens_prompt=tokens_prompt,
            tokens_completion=tokens_completion,
            embedding_count=embedding_count,
            rerank_count=rerank_count,
            ms_total=ms_total,
            storage_bytes=storage_bytes,
        )
