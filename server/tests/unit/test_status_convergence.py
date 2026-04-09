from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.v1.modelhub.handlers import ModelHubHandlers
from app.kernel.execution.state_machine import RunStatus, StepStatus
from app.kernel.runtime.contracts.status import ExecutionStatus
from app.modules.modelhub.application.service import ModelHubService
from app.modules.plugin.application.service import PluginService


def test_plugin_publish_status_helpers():
    assert PluginService.publish_status_for(SimpleNamespace(published=False)) == "draft"
    assert PluginService.publish_status_for(SimpleNamespace(published=True)) == "published"
    assert PluginService.resolve_published_flag(publish_status="published", current=False) is True
    assert PluginService.resolve_published_flag(publish_status="draft", current=True) is False


def test_modelhub_service_status_normalizers():
    service = object.__new__(ModelHubService)

    assert service.provider_model_status(True) == "active"
    assert service.provider_model_status(False) == "disabled"
    assert service.platform_model_status(True) == "active"
    assert service.platform_model_status(False) == "disabled"
    assert service._normalize_model_enabled(status="active", enabled=None, current=False) is True
    assert service._normalize_model_enabled(status="disabled", enabled=True, current=True) is False
    assert service._resolve_lifecycle_status(lifecycle_status="deprecated", lifecycle="ga", current=None) == "deprecated"
    assert service._resolve_lifecycle_status(lifecycle_status=None, lifecycle="ga", current=None) == "ga"


def test_modelhub_handlers_expose_new_and_compat_status_fields():
    service = object.__new__(ModelHubService)
    handler = ModelHubHandlers(service)
    now = datetime.now(timezone.utc)

    platform_payload = handler._as_platform_model_response(
        SimpleNamespace(
            id="plm_1",
            provider_kind="openai",
            model_id="gpt-5.1",
            display_name="GPT-5.1",
            capabilities_json={"capabilities": ["chat"]},
            context_window=128000,
            max_output_tokens=8192,
            lifecycle="ga",
            raw_meta={},
            is_active=True,
            last_seen_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    assert platform_payload.status == "active"
    assert platform_payload.lifecycle_status == "ga"
    assert platform_payload.lifecycle == "ga"
    assert platform_payload.is_active is True

    provider_model_payload = handler._as_provider_model_response(
        SimpleNamespace(
            id="pmod_1",
            provider_id="prov_1",
            provider_kind="openai",
            model_id="gpt-5.1",
            display_name="GPT-5.1",
            description="primary",
            capabilities_json={"capabilities": ["chat"]},
            config_json={},
            context_window=128000,
            max_output_tokens=8192,
            lifecycle="deprecated",
            raw_meta={},
            enabled=False,
            source="platform",
            platform_model_id="plm_1",
            sync_status="platform_removed",
            user_overrides_json={},
            last_synced_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    assert provider_model_payload.status == "disabled"
    assert provider_model_payload.lifecycle_status == "deprecated"
    assert provider_model_payload.lifecycle == "deprecated"
    assert provider_model_payload.enabled is False


def test_legacy_state_machine_statuses_share_runtime_execution_values():
    assert RunStatus.RUNNING.value == ExecutionStatus.RUNNING.value
    assert RunStatus.SUCCEEDED.value == ExecutionStatus.SUCCEEDED.value
    assert StepStatus.CANCELED.value == ExecutionStatus.CANCELED.value
