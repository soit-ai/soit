"""rebuild_projections

Recompute and validate projection summaries for workflow and agent versions.

The retired legacy projection tables no longer exist. This maintenance script
rebuilds the current in-memory projection view from canonical version specs and
verifies that the stored specs remain valid.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, select

from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.kernel.projections.agent_projection import build_agent_refs
from app.kernel.projections.workflow_projection import (
    build_workflow_components,
    build_workflow_edges,
    build_workflow_refs,
)
from app.kernel.specs.validator import validate_runtime_spec
from app.modules.agent.domain.models import AgentVersion
from app.modules.workflow.domain.models import WorkflowVersion


SUPPORTED_SPEC_SCHEMAS = {"workflow.v1", "agent.v1"}


@dataclass(frozen=True)
class ProjectionSummary:
    subject_type: str
    subject_id: str
    version_id: str
    spec_schema: str
    details: dict[str, int]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild workflow/agent projection summaries.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--workflow-id")
    parser.add_argument("--agent-id")
    parser.add_argument("--version-id")
    parser.add_argument("--spec-schema", help="Filter by spec schema (workflow.v1/agent.v1).")
    parser.add_argument("--all", action="store_true", help="Process all matching versions.")
    return parser.parse_args()


def _normalize_schema(spec_schema: str | None) -> str | None:
    if spec_schema is None:
        return None
    normalized = spec_schema.strip().lower()
    if normalized not in SUPPORTED_SPEC_SCHEMAS:
        supported = ", ".join(sorted(SUPPORTED_SPEC_SCHEMAS))
        raise ValueError(f"Unsupported spec schema: {spec_schema}. Supported: {supported}")
    return normalized


def _workflow_versions(db, ctx: RequestContext, *, workflow_id: str | None = None, version_id: str | None = None) -> list[WorkflowVersion]:
    clauses = [
        WorkflowVersion.tenant_id == ctx.tenant_id,
        WorkflowVersion.workspace_id == ctx.workspace_id,
    ]
    if workflow_id:
        clauses.append(WorkflowVersion.workflow_id == workflow_id)
    if version_id:
        clauses.append(WorkflowVersion.id == version_id)
    query = select(WorkflowVersion).where(and_(*clauses)).order_by(WorkflowVersion.created_at.asc())
    return list(db.exec(query).all())


def _agent_versions(db, ctx: RequestContext, *, agent_id: str | None = None, version_id: str | None = None) -> list[AgentVersion]:
    clauses = [
        AgentVersion.tenant_id == ctx.tenant_id,
        AgentVersion.workspace_id == ctx.workspace_id,
    ]
    if agent_id:
        clauses.append(AgentVersion.agent_id == agent_id)
    if version_id:
        clauses.append(AgentVersion.id == version_id)
    query = select(AgentVersion).where(and_(*clauses)).order_by(AgentVersion.created_at.asc())
    return list(db.exec(query).all())


def _build_workflow_summary(version: WorkflowVersion) -> ProjectionSummary:
    spec_json = version.spec_json or {}
    validate_runtime_spec(version.spec_schema, spec_json, raise_on_error=True)
    components = build_workflow_components(spec_json)
    edges = build_workflow_edges(spec_json)
    refs = build_workflow_refs(spec_json)
    return ProjectionSummary(
        subject_type="workflow",
        subject_id=version.workflow_id,
        version_id=version.id,
        spec_schema=version.spec_schema,
        details={
            "components": len(components),
            "edges": len(edges),
            "refs": len(refs),
        },
    )


def _build_agent_summary(version: AgentVersion) -> ProjectionSummary:
    spec_json = version.spec_json or {}
    validate_runtime_spec(version.spec_schema, spec_json, raise_on_error=True)
    refs = build_agent_refs(spec_json)
    return ProjectionSummary(
        subject_type="agent",
        subject_id=version.agent_id,
        version_id=version.id,
        spec_schema=version.spec_schema,
        details={"refs": len(refs)},
    )


def _iter_summaries(db, ctx: RequestContext, args: argparse.Namespace) -> Iterable[ProjectionSummary]:
    spec_schema = _normalize_schema(args.spec_schema)

    if args.version_id:
        workflow_versions = _workflow_versions(db, ctx, version_id=args.version_id)
        if workflow_versions:
            for version in workflow_versions:
                yield _build_workflow_summary(version)
            return

        agent_versions = _agent_versions(db, ctx, version_id=args.version_id)
        if agent_versions:
            for version in agent_versions:
                yield _build_agent_summary(version)
            return

        raise LookupError(f"Version not found: {args.version_id}")

    if args.workflow_id:
        versions = _workflow_versions(db, ctx, workflow_id=args.workflow_id)
        if not versions:
            raise LookupError(f"Workflow not found or has no versions: {args.workflow_id}")
        for version in versions:
            if spec_schema and version.spec_schema != spec_schema:
                continue
            yield _build_workflow_summary(version)
        return

    if args.agent_id:
        versions = _agent_versions(db, ctx, agent_id=args.agent_id)
        if not versions:
            raise LookupError(f"Agent not found or has no versions: {args.agent_id}")
        for version in versions:
            if spec_schema and version.spec_schema != spec_schema:
                continue
            yield _build_agent_summary(version)
        return

    if args.all:
        workflow_versions = _workflow_versions(db, ctx)
        for version in workflow_versions:
            if spec_schema and version.spec_schema != spec_schema:
                continue
            yield _build_workflow_summary(version)

        agent_versions = _agent_versions(db, ctx)
        for version in agent_versions:
            if spec_schema and version.spec_schema != spec_schema:
                continue
            yield _build_agent_summary(version)
        return

    raise ValueError("No targets specified. Use --version-id, --workflow-id, --agent-id, or --all.")


def _print_summary(summary: ProjectionSummary) -> None:
    metrics = " ".join(f"{key}={value}" for key, value in summary.details.items())
    print(
        f"[OK] {summary.subject_type}={summary.subject_id} "
        f"version={summary.version_id} schema={summary.spec_schema} {metrics}"
    )


def main() -> int:
    args = _parse_args()
    ctx = RequestContext(
        tenant_id=args.tenant_id,
        workspace_id=args.workspace_id,
        user_id=args.user_id,
    )
    db = get_db_sync()
    try:
        summaries = list(_iter_summaries(db, ctx, args))
    except (LookupError, ValueError) as exc:
        print(str(exc))
        db.close()
        return 1
    except Exception as exc:
        print(f"Projection rebuild failed: {exc}")
        db.close()
        return 1

    try:
        if not summaries:
            print("No matching versions found.")
            return 1
        for summary in summaries:
            _print_summary(summary)
        print(f"Rebuilt {len(summaries)} projection summaries.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
