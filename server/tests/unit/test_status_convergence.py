from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.v1.modelhub.handlers import ModelHubHandlers
from app.kernel.execution.state_machine import RunStatus, StepStatus
from app.kernel.runtime.status import ExecutionStatus
from app.modules.modelhub.application.service import ModelHubService
from app.modules.plugin.application.service import PluginService


def test_plugin_publish_status_helpers():
    assert PluginService.publish_status_for(SimpleNamespace(publish_status="draft")) == "draft"
    assert PluginService.publish_status_for(SimpleNamespace(publish_status="published")) == "published"
    assert PluginService.normalize_publish_status("published", current="draft") == "published"
    assert PluginService.normalize_publish_status("archived", current="published") == "archived"


def test_modelhub_service_status_normalizers():
    service = object.__new__(ModelHubService)

    assert service.normalize_model_status("active", current="disabled") == "active"
    assert service.normalize_model_status("disabled", current="active") == "disabled"
    assert service.normalize_model_status(None, current="active") == "active"


def test_modelhub_handlers_expose_canonical_status_fields_only():
    service = object.__new__(ModelHubService)
    handler = ModelHubHandlers(service)
    now = datetime.now(UTC)

    platform_payload = handler._as_platform_model_response(
        SimpleNamespace(
            id="plm_1",
            provider_kind="openai",
            model_id="gpt-5.1",
            display_name="GPT-5.1",
            capabilities_json={"capabilities": ["chat"]},
            context_window=128000,
            max_output_tokens=8192,
            lifecycle_status="ga",
            raw_meta={},
            status="active",
            last_seen_at=None,
            created_at=now,
            updated_at=now,
        )
    )
    assert platform_payload.status == "active"
    assert platform_payload.lifecycle_status == "ga"
    assert not hasattr(platform_payload, "lifecycle")
    assert not hasattr(platform_payload, "is_active")

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
            lifecycle_status="deprecated",
            raw_meta={},
            status="disabled",
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
    assert provider_model_payload.architecture_json is None
    assert provider_model_payload.capability_matrix_json is None
    assert provider_model_payload.parameter_config_json is None
    assert provider_model_payload.pricing_json is None
    assert provider_model_payload.diagnostics_json is None
    assert not hasattr(provider_model_payload, "lifecycle")
    assert not hasattr(provider_model_payload, "enabled")
    assert not hasattr(provider_model_payload, "is_active")


def test_legacy_state_machine_statuses_share_runtime_execution_values():
    assert RunStatus.RUNNING.value == ExecutionStatus.RUNNING.value
    assert RunStatus.SUCCEEDED.value == ExecutionStatus.SUCCEEDED.value
    assert StepStatus.CANCELED.value == ExecutionStatus.CANCELED.value
