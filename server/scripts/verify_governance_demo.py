"""Build a deterministic 20-minute governance demo evidence report."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy import and_, select

from app.infra.db.session import get_db_sync
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.runs import RunCostEntry, RunStep
from app.kernel.runtime.runs.service import RunService
from app.modules.secrets.domain.models import Secret
from scripts.evaluate_support_ticket_regression import (
    DEFAULT_CASES_PATH,
    evaluate_support_ticket_regression,
)
from scripts.seed_enterprise_mvp_scenarios import seed_enterprise_mvp_scenarios


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the 20-minute SOIT governance demo evidence chain.")
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


def _count_seed_secrets(db, ctx: RequestContext) -> int:
    rows = db.exec(
        select(Secret).where(
            and_(
                Secret.tenant_id == ctx.tenant_id,
                Secret.workspace_id == ctx.workspace_id,
            )
        )
    ).all()
    return sum(1 for row in rows if "enterprise_mvp_scenarios" in str((_unwrap(row).description or "")))


def _count_cost_entries(db, ctx: RequestContext, run_id: str) -> int:
    rows = db.exec(
        select(RunCostEntry).where(
            and_(
                RunCostEntry.tenant_id == ctx.tenant_id,
                RunCostEntry.workspace_id == ctx.workspace_id,
                RunCostEntry.run_id == run_id,
            )
        )
    ).all()
    return len(rows)


def _count_steps(db, ctx: RequestContext, run_id: str) -> int:
    rows = db.exec(
        select(RunStep).where(
            and_(
                RunStep.tenant_id == ctx.tenant_id,
                RunStep.workspace_id == ctx.workspace_id,
                RunStep.run_id == run_id,
            )
        )
    ).all()
    return len(rows)


def _demo_steps(run_url: str) -> list[dict[str, Any]]:
    return [
        {
            "section": "permissions",
            "minutes": 3,
            "talk_track": "Show workspace-scoped Agent bindings and plugin capability access under the Owner role.",
            "evidence_route": "/agents",
        },
        {
            "section": "secrets",
            "minutes": 3,
            "talk_track": "Show managed secret inventory used by governed tool and connector calls.",
            "evidence_route": "/settings/secrets",
        },
        {
            "section": "call_audit",
            "minutes": 4,
            "talk_track": "Open Audit Explorer and inspect policy-gateway request and response evidence.",
            "evidence_route": "/observe/audits?gateway_type=tool",
        },
        {
            "section": "cost_attribution",
            "minutes": 3,
            "talk_track": "Show run-level cost attribution for model/tool execution.",
            "evidence_route": run_url,
        },
        {
            "section": "replay",
            "minutes": 4,
            "talk_track": "Replay the run detail: steps, tool calls, citations, audits, child runs, and costs.",
            "evidence_route": run_url,
        },
        {
            "section": "regression",
            "minutes": 3,
            "talk_track": "Show regression replay as the publish gate for the next Agent version.",
            "evidence_route": "/agents",
        },
    ]


async def verify_governance_demo(db, args: argparse.Namespace) -> dict[str, Any]:
    """Seed, evaluate, and summarize the demo evidence chain."""
    scenario_summary = await seed_enterprise_mvp_scenarios(
        db,
        argparse.Namespace(
            email=args.email,
            password=args.password,
            name=args.name,
            tenant_name=args.tenant_name,
            workspace_name=args.workspace_name,
            profile="broad",
            reset=True,
            json_output=None,
        ),
    )
    regression_report = await evaluate_support_ticket_regression(db, args)
    ctx = RequestContext(
        tenant_id=scenario_summary.tenant_id,
        workspace_id=scenario_summary.workspace_id,
        user_id=scenario_summary.user_id,
        tenant_role="Owner",
        workspace_role="Owner",
    )
    regression_case = next(
        case for case in regression_report["cases"] if case["audit_count"] >= 1 and case["cost"]["entries"] >= 1
    )
    run_id = regression_case["run_id"]
    detail = RunService(db=db, ctx=ctx).get_run(run_id)
    run_url = f"/observe/runs/{run_id}"

    evidence = {
        "permissions": {
            "passed": ctx.workspace_role == "Owner" and len(scenario_summary.agent_chain_refs) >= 1,
            "tenant_id": ctx.tenant_id,
            "workspace_id": ctx.workspace_id,
            "workspace_role": ctx.workspace_role,
            "agent_binding_chains": len(scenario_summary.agent_chain_refs),
            "plugin_refs": scenario_summary.plugin_refs,
        },
        "secrets": {
            "passed": _count_seed_secrets(db, ctx) >= 2,
            "secret_count": _count_seed_secrets(db, ctx),
            "secret_ids": scenario_summary.secret_ids,
        },
        "call_audit": {
            "passed": len(detail.audits) >= 1,
            "run_id": run_id,
            "audit_count": len(detail.audits),
            "gateway_types": sorted({audit.gateway_type for audit in detail.audits if audit.gateway_type}),
        },
        "cost_attribution": {
            "passed": _count_cost_entries(db, ctx, run_id) >= 1,
            "run_id": run_id,
            "cost_entries": _count_cost_entries(db, ctx, run_id),
            "cost": regression_case["cost"],
        },
        "replay": {
            "passed": _count_steps(db, ctx, run_id) >= 1 and len(detail.citations) >= 1 and len(detail.audits) >= 1,
            "run_id": run_id,
            "run_explorer_url": run_url,
            "step_count": _count_steps(db, ctx, run_id),
            "citation_count": len(detail.citations),
            "child_run_count": len(detail.child_runs),
            "audit_count": len(detail.audits),
        },
        "regression": {
            "passed": bool(regression_report["passed"]),
            "summary": regression_report["summary"],
            "case_ids": [case["case_id"] for case in regression_report["cases"]],
        },
    }
    demo_steps = _demo_steps(run_url)
    report = {
        "scenario": "governance_demo_20_min",
        "passed": all(item["passed"] for item in evidence.values()),
        "tenant_id": ctx.tenant_id,
        "workspace_id": ctx.workspace_id,
        "summary": {
            "demo_minutes": sum(step["minutes"] for step in demo_steps),
            "sections": len(demo_steps),
            "run_id": run_id,
        },
        "demo_steps": demo_steps,
        "evidence": evidence,
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
        report = asyncio.run(verify_governance_demo(db, args))
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["passed"] else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
