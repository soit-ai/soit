"""preflight

Preflight checks for workflow external references.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.kernel.contracts.context import RequestContext
from app.kernel.commons.errors import ValidationError
from app.kernel.registry.deps import get_registry
from app.kernel.projections.workflow_projection import build_workflow_refs
from app.kernel.projections.chat_projection import build_chat_refs
from app.kernel.projections.bot_projection import build_bot_refs
from app.kernel.projections.agent_projection import build_agent_refs
from app.modules.dataset.infra.repository import DatasetRepository
from app.modules.modelhub.infra.repository import ProviderModelRepository
from app.modules.secrets.infra.repository import SecretRepository
from app.modules.pluginmarket.infra.repository import PluginRepository
from app.modules.appcenter.infra.repository import AppRepository


class PreflightChecker:
    """Validate external references before publish/run."""

    def __init__(self, db: Session, ctx: RequestContext):
        self.db = db
        self.ctx = ctx
        self.dataset_repo = DatasetRepository(db, ctx)
        self.model_repo = ProviderModelRepository(db, ctx)
        self.secret_repo = SecretRepository(db, ctx)
        self.plugin_repo = PluginRepository(db, ctx)
        self.app_repo = AppRepository(db, ctx)

    def check(self, spec_json: Dict[str, Any], spec_schema: str) -> None:
        normalized = (spec_schema or "").lower()
        if normalized == "workflow.v1":
            refs = build_workflow_refs(spec_json)
        elif normalized == "chat.v1":
            refs = build_chat_refs(spec_json)
        elif normalized == "bot.v1":
            refs = build_bot_refs(spec_json)
        elif normalized == "agent.v1":
            refs = build_agent_refs(spec_json)
        else:
            return
        issues: List[Dict[str, Any]] = []
        for ref in refs:
            ref_type = ref.get("ref_type")
            ref_id = ref.get("ref_id")
            ref_key = ref.get("ref_key")
            path = ref.get("spec_path")
            ok = self._check_ref(ref_type, ref_id, ref_key)
            if not ok:
                issues.append(
                    {
                        "ref_type": ref_type,
                        "ref_id": ref_id,
                        "ref_key": ref_key,
                        "spec_path": path,
                    }
                )
        if issues:
            raise ValidationError("Preflight checks failed", {"missing_refs": issues})

    def _check_ref(self, ref_type: Optional[str], ref_id: Optional[str], ref_key: Optional[str]) -> bool:
        if not ref_type:
            return True
        if ref_type == "model":
            value = ref_key or ref_id
            if not value:
                return False
            provider_kind, model_id = _parse_model_ref(value)
            if provider_kind and model_id:
                return (
                    self.model_repo.get_by_provider_kind_and_model_id(provider_kind, model_id)
                    is not None
                )
            return self.model_repo.get_by_id(value) is not None
        if ref_type == "dataset":
            value = _strip_prefix(ref_key) if ref_key else ref_id
            if not value:
                return False
            return self.dataset_repo.get_by_id(value) is not None
        if ref_type == "secret":
            value = _strip_prefix(ref_key) if ref_key else ref_id
            if not value:
                return False
            return self.secret_repo.get_by_id(value) is not None
        if ref_type == "plugin":
            value = _strip_prefix(ref_key) if ref_key else ref_id
            if not value:
                return False
            return self.plugin_repo.get_by_id(value) is not None
        if ref_type == "app":
            value = _strip_prefix(ref_key) if ref_key else ref_id
            if not value:
                return False
            return self.app_repo.get_by_id(value) is not None
        if ref_type == "tool":
            ref_value = ref_key or ref_id
            if not ref_value:
                return False
            reg = get_registry()
            found = reg.get_latest(
                kind="tool",
                tenant_id=self.ctx.tenant_id,
                workspace_id=self.ctx.workspace_id,
                name=ref_value,
            )
            return found is not None
        return True


def _strip_prefix(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if ":" not in value:
        return value
    return value.split(":", 1)[1]


def _parse_model_ref(value: str) -> tuple[Optional[str], Optional[str]]:
    if not value:
        return None, None
    if value.startswith("model:"):
        parts = value.split(":")
        if len(parts) >= 3:
            return parts[1], ":".join(parts[2:])
        return None, None
    if ":" in value:
        provider_kind, model_id = value.split(":", 1)
        return provider_kind, model_id
    return None, None
