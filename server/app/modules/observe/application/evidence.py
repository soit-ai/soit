"""Run evidence bundles.

One run's evidence as a single file a reviewer can take away: the run, its
steps, costs and audit entries in the ledger contract, and beside them the
tool calls, approvals, citations, content safety findings, policy bundle ids
and governance matrix the run detail shows. ``manifest.json`` names every
file with its SHA-256, and ``SHA256SUMS`` lists the same digests in the
format ``sha256sum -c`` checks.

The bundle keeps no more content than the run's workspace does: when it
records metadata only, tool arguments and results, approval details and
citation text are replaced by a length and a hash, like the run's own
summaries. The archive is deterministic: an unchanged run always gives the
same bytes, so a bundle's own digest identifies the evidence it holds. Who
downloaded it, and when, is written to the audit ledger instead.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import zipfile
from dataclasses import dataclass
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.kernel.commons.errors import NotFoundError
from app.kernel.contracts.context import RequestContext
from app.kernel.runtime.db.models.audit import AuditEvent
from app.kernel.runtime.db.models.runs import Run, RunCostEntry, RunStep
from app.kernel.runtime.runs import ledger
from app.kernel.runtime.runs.content_capture import (
    CAPTURE_FULL,
    CAPTURE_METADATA_ONLY,
    get_workspace_capture_lookup,
    withheld,
)
from app.kernel.runtime.runs.service import RunService
from app.modules.observe.domain.models import ApprovalRequest

logger = logging.getLogger(__name__)

EVIDENCE_SCHEMA = "soit.evidence"
EVIDENCE_VERSION = "1.0"
_POLICY_KEYS = frozenset({"tenant_bundle_id", "workspace_bundle_id", "policy_bundle_id"})
_CITATION_TEXT_KEYS = ("snippet", "text", "title", "source_uri", "section_path")
# The DOS epoch: fixed entry times make the archive reproducible.
_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class EvidenceBundle:
    filename: str
    content: bytes
    manifest: dict[str, Any]


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, indent=2).encode() + b"\n"


def _jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode() + b"\n" for row in rows
    )


def _withheld_value(value: Any) -> str | None:
    if value in (None, "", {}, []):
        return None
    text = value if isinstance(value, str) else json.dumps(value, sort_keys=True, default=str)
    return withheld(text)


def _policy_bundle_ids(value: Any, found: set[str]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _POLICY_KEYS and isinstance(item, str) and item:
                found.add(item)
            else:
                _policy_bundle_ids(item, found)
    elif isinstance(value, list):
        for item in value:
            _policy_bundle_ids(item, found)


class RunEvidenceService:
    """Build the evidence bundle of one run in the caller's workspace."""

    def __init__(self, db: AsyncSession, ctx: RequestContext) -> None:
        self.db = db
        self.ctx = ctx

    async def _capture_mode(self) -> str:
        """What the bundle may keep of content.

        Authentication resolves the workspace's mode, tightened by the key's,
        into the context. A context without it reads the workspace; a bundle
        that cannot tell withholds content rather than risk handing out what
        the workspace keeps back.
        """
        mode = self.ctx.content_capture
        if mode is None:
            lookup = get_workspace_capture_lookup()
            if lookup is None:
                return CAPTURE_METADATA_ONLY
            try:
                mode = await lookup(self.db, self.ctx.tenant_id, self.ctx.workspace_id)
            except Exception:
                logger.warning("Content capture lookup failed; withholding content", exc_info=True)
                return CAPTURE_METADATA_ONLY
        return CAPTURE_METADATA_ONLY if mode == CAPTURE_METADATA_ONLY else CAPTURE_FULL

    async def _rows(self, model: Any, run_id: str, order: Any) -> list[Any]:
        query = (
            select(model)
            .where(
                model.run_id == run_id,
                model.tenant_id == self.ctx.tenant_id,
                model.workspace_id == self.ctx.workspace_id,
            )
            .order_by(order, model.id)
        )
        return list((await self.db.exec(query)).all())

    async def build(self, run_id: str) -> EvidenceBundle:
        run = await self.db.get(Run, run_id)
        if (
            run is None
            or run.tenant_id != self.ctx.tenant_id
            or run.workspace_id != self.ctx.workspace_id
        ):
            raise NotFoundError(f"Run not found: {run_id}")
        detail = await RunService(self.db, self.ctx).get_run(run_id)
        keeps_content = await self._capture_mode() == CAPTURE_FULL

        steps = await self._rows(RunStep, run_id, RunStep.started_at)
        costs = await self._rows(RunCostEntry, run_id, RunCostEntry.created_at)
        audits = await self._rows(AuditEvent, run_id, AuditEvent.created_at)
        approvals = await self._rows(ApprovalRequest, run_id, ApprovalRequest.created_at)

        tool_calls = []
        for call in detail.tool_calls:
            row = call.model_dump(mode="json")
            if not keeps_content:
                for key in ("arguments_json", "result_json", "error_message"):
                    row[key] = _withheld_value(row.get(key))
            tool_calls.append(row)

        approval_rows = [
            {
                "approval_id": item.id,
                "run_id": item.run_id,
                "task_id": item.task_id,
                "title": item.title if keeps_content else _withheld_value(item.title),
                "policy_ref": item.policy_ref,
                "status": item.status,
                "requested_by": item.requested_by,
                "resolved_by": item.resolved_by,
                "resolution_note": (
                    item.resolution_note if keeps_content else _withheld_value(item.resolution_note)
                ),
                "details": item.details_json if keeps_content else _withheld_value(item.details_json),
                "resolved_at": ledger.iso_utc(item.resolved_at),
                "created_at": ledger.iso_utc(item.created_at),
            }
            for item in approvals
        ]

        citations = []
        for citation in detail.citations:
            row = dict(citation)
            if not keeps_content:
                for key in _CITATION_TEXT_KEYS:
                    if key in row:
                        row[key] = _withheld_value(row[key])
            citations.append(row)

        safety_findings = [
            {"step_record_id": step.id, "step_id": step.step_id, **finding}
            for step in steps
            for finding in ((step.metrics_json or {}).get("content_safety") or [])
            if isinstance(finding, dict)
        ]

        bundle_ids: set[str] = set()
        for step in steps:
            _policy_bundle_ids(step.metrics_json, bundle_ids)
        for audit in audits:
            _policy_bundle_ids(audit.payload_json, bundle_ids)

        files: dict[str, tuple[bytes, int]] = {
            "run.json": (_json(ledger.envelope("run", ledger.run_record(run))), 1),
            "steps.jsonl": (
                _jsonl([ledger.envelope("step", ledger.step_record(step)) for step in steps]),
                len(steps),
            ),
            "costs.jsonl": (
                _jsonl([ledger.envelope("cost", ledger.cost_record(entry)) for entry in costs]),
                len(costs),
            ),
            "audit.jsonl": (
                _jsonl([ledger.envelope("audit", ledger.audit_record(event)) for event in audits]),
                len(audits),
            ),
            "tool_calls.jsonl": (_jsonl(tool_calls), len(tool_calls)),
            "approvals.jsonl": (_jsonl(approval_rows), len(approval_rows)),
            "citations.jsonl": (_jsonl(citations), len(citations)),
            "content_safety.jsonl": (_jsonl(safety_findings), len(safety_findings)),
            "policy.json": (_json({"policy_bundle_ids": sorted(bundle_ids)}), len(bundle_ids)),
            "governance.json": (
                _json([item.model_dump(mode="json") for item in detail.governance_evidence]),
                len(detail.governance_evidence),
            ),
        }
        manifest = {
            "schema": EVIDENCE_SCHEMA,
            "version": EVIDENCE_VERSION,
            "ledger_schema_version": ledger.LEDGER_SCHEMA_VERSION,
            "run_id": run.id,
            "tenant_id": run.tenant_id,
            "workspace_id": run.workspace_id,
            "run_status": run.status,
            "content_capture": CAPTURE_FULL if keeps_content else CAPTURE_METADATA_ONLY,
            "child_run_ids": sorted(child.id for child in detail.child_runs),
            "run_updated_at": ledger.iso_utc(run.updated_at),
            "files": [
                {
                    "path": path,
                    "sha256": hashlib.sha256(body).hexdigest(),
                    "bytes": len(body),
                    "records": records,
                }
                for path, (body, records) in sorted(files.items())
            ],
        }
        manifest_body = _json(manifest)
        digests = {path: hashlib.sha256(body).hexdigest() for path, (body, _) in files.items()}
        digests["manifest.json"] = hashlib.sha256(manifest_body).hexdigest()
        sums = "".join(f"{digests[path]}  {path}\n" for path in sorted(digests)).encode()

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            entries = {**{path: body for path, (body, _) in files.items()}, "manifest.json": manifest_body}
            entries["SHA256SUMS"] = sums
            for path in sorted(entries):
                info = zipfile.ZipInfo(f"evidence-{run.id}/{path}", date_time=_ZIP_TIME)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                bundle.writestr(info, entries[path])
        return EvidenceBundle(
            filename=f"soit-evidence-{run.id}.zip",
            content=archive.getvalue(),
            manifest=manifest,
        )
