"""The production reference must satisfy the runtime's own production rules.

A deployment file that merely looks hardened is worth nothing. These contracts
derive settings from the compose file itself and run the same validation the
API runs at startup, and they check that every alert names a metric the runtime
actually exports.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from app.settings.settings import Settings

ROOT = Path(__file__).resolve().parents[2].parent
COMPOSE_PATH = ROOT / "docker" / "docker-compose.production.yml"
PRODUCTION_DIR = ROOT / "docker" / "production"
ALERTS_PATH = PRODUCTION_DIR / "alerts.yaml"
COLLECTOR_PATH = PRODUCTION_DIR / "otel-collector.yaml"
CADDYFILE_PATH = PRODUCTION_DIR / "Caddyfile"
METRICS_PATH = Path(__file__).resolve().parents[2] / "app" / "kernel" / "observe" / "metrics.py"

_VAR_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?(?::\?[^}]*)?\}")

# Values an operator supplies. Chosen to be valid so the contract exercises the
# runtime's rules rather than the placeholder's shape.
OPERATOR_SUPPLIED = {
    "DATABASE_URL": "postgresql://soit:secret@db.internal:5432/soit",
    "REDIS_URL": "redis://cache.internal:6379/0",
    "EVENT_BUS_REDIS_URL": "redis://cache.internal:6379/1",
    "SECRET_KEY": "p" * 48,
    "VAULT_URL": "https://vault.internal:8200",
    "VAULT_TOKEN": "hvs.operator-token",
    "STORAGE_OPTIONS_JSON": '{"endpoint_url":"https://s3.internal"}',
    "MILVUS_HOST": "milvus.internal",
    "PLUGIN_SIGNATURE_PUBLIC_KEYS": '["dHJ1c3RlZC1rZXk="]',
    "SOIT_PUBLIC_HOSTNAME": "soit.example.com",
    "OPENAI_API_KEY": "sk-operator",
}


def _load_compose() -> dict:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def _resolve(value: object) -> str:
    """Expand compose interpolation the way `docker compose` would."""
    text = str(value)

    def replace(match: re.Match[str]) -> str:
        name, default = match.group(1), match.group(2)
        if name in OPERATOR_SUPPLIED:
            return OPERATOR_SUPPLIED[name]
        return default if default is not None else ""

    return _VAR_RE.sub(replace, text)


def _service_env(service: str) -> dict[str, str]:
    compose = _load_compose()
    raw = compose["services"][service].get("environment") or {}
    return {key: _resolve(value) for key, value in raw.items()}


def _settings_from(env: dict[str, str]) -> Settings:
    def flag(name: str, default: bool = False) -> bool:
        return str(env.get(name, default)).strip().lower() in {"true", "1", "yes"}

    return Settings(
        _env_file=None,
        environment=env["ENVIRONMENT"],
        database_url=env["DATABASE_URL"],
        redis_url=env["REDIS_URL"],
        secret_key=env["SECRET_KEY"],
        vault_url=env["VAULT_URL"],
        vault_token=env["VAULT_TOKEN"],
        openai_api_key=env.get("OPENAI_API_KEY") or None,
        event_bus_backend=env["EVENT_BUS_BACKEND"],
        response_interaction_inline_execution=flag("RESPONSE_INTERACTION_INLINE_EXECUTION"),
        response_interaction_worker_enabled=flag("RESPONSE_INTERACTION_WORKER_ENABLED"),
        outbox_dispatcher_enabled=flag("OUTBOX_DISPATCHER_ENABLED"),
        otel_enabled=flag("OTEL_ENABLED"),
        otel_exporter_otlp_endpoint=env["OTEL_EXPORTER_OTLP_ENDPOINT"],
        plugin_signature_required=flag("PLUGIN_SIGNATURE_REQUIRED"),
        plugin_signature_public_keys=["trusted-key"],
        plugin_integrity_required=flag("PLUGIN_INTEGRITY_REQUIRED"),
        content_safety_enabled=flag("CONTENT_SAFETY_ENABLED"),
        content_safety_endpoint=env.get("CONTENT_SAFETY_ENDPOINT") or None,
    )


def test_the_api_service_satisfies_production_validation() -> None:
    # The same check the API runs at startup, applied to the shipped file.
    _settings_from(_service_env("api")).validate_runtime_requirements()


def test_the_dispatcher_runs_as_its_own_process() -> None:
    api_env = _service_env("api")
    dispatcher_env = _service_env("outbox-dispatcher")

    # Production refuses an in-process dispatcher, so the API must leave it off
    # and a dedicated service must turn it on.
    assert api_env["OUTBOX_DISPATCHER_ENABLED"] == "false"
    assert dispatcher_env["OUTBOX_DISPATCHER_ENABLED"] == "true"
    with pytest.raises(ValueError, match="dedicated outbox dispatcher"):
        _settings_from(dispatcher_env).validate_runtime_requirements()


def test_execution_never_runs_inside_the_api_request() -> None:
    env = _service_env("api")

    assert env["RESPONSE_INTERACTION_INLINE_EXECUTION"] == "false"
    assert env["RESPONSE_INTERACTION_WORKER_ENABLED"] == "true"
    assert env["WORKFLOW_ORPHAN_REAPER_ENABLED"] == "true"


def test_the_ingest_worker_is_not_bounded_by_task_count() -> None:
    env = _service_env("knowledge-ingest-worker")

    # A positive limit makes the worker exit and the container restart after a
    # few documents.
    assert env["KNOWLEDGE_INGEST_WORKER_MAX_TASKS"] == "0"


def test_no_stateful_infrastructure_is_bundled() -> None:
    services = set(_load_compose()["services"])

    # Running the database, cache, object store or secret manager as disposable
    # sibling containers is what makes a "production" compose file untrue.
    assert not services & {"postgres", "redis", "minio", "vault", "etcd", "milvus"}


def test_only_the_tls_gateway_is_published() -> None:
    compose = _load_compose()

    published = {
        name: service.get("ports")
        for name, service in compose["services"].items()
        if service.get("ports")
    }
    assert set(published) == {"gateway"}
    assert "expose" in compose["services"]["api"]


def test_the_gateway_terminates_tls_and_does_not_buffer_event_streams() -> None:
    caddyfile = CADDYFILE_PATH.read_text(encoding="utf-8")

    assert "Strict-Transport-Security" in caddyfile
    # Buffering would hold server-sent events until the response completed.
    assert "flush_interval -1" in caddyfile


def test_the_collector_drops_attributes_that_carry_customer_data() -> None:
    collector = yaml.safe_load(COLLECTOR_PATH.read_text(encoding="utf-8"))

    deleted = {
        action["key"]
        for action in collector["processors"]["attributes/redact"]["actions"]
        if action.get("action") == "delete"
    }
    assert {"soit.input_summary", "soit.output_summary"} <= deleted
    assert collector["service"]["pipelines"]["traces"]["processors"][0] == "memory_limiter"


def test_every_alert_references_a_metric_the_runtime_exports() -> None:
    metrics_source = METRICS_PATH.read_text(encoding="utf-8")
    exported = set(re.findall(r'"(soit_[a-z0-9_]+)"', metrics_source))
    assert exported, "no metrics were discovered; the contract would be vacuous"

    rules = yaml.safe_load(ALERTS_PATH.read_text(encoding="utf-8"))
    referenced: set[str] = set()
    for group in rules["groups"]:
        for rule in group["rules"]:
            referenced |= set(re.findall(r"\bsoit_[a-z0-9_]+\b", rule["expr"]))

    assert referenced, "alert rules reference no runtime metric"
    # Histogram queries address the generated _bucket series.
    unknown = {
        name
        for name in referenced
        if name not in exported and name.removesuffix("_bucket") not in exported
    }
    # A rule naming a metric that is never emitted never fires, which reads as
    # coverage while providing none.
    assert unknown == set()


def test_alerts_cover_the_failure_modes_this_runtime_actually_has() -> None:
    rules = yaml.safe_load(ALERTS_PATH.read_text(encoding="utf-8"))
    names = {rule["alert"] for group in rules["groups"] for rule in group["rules"]}

    assert {
        "SoitOutboxDeadLetters",
        "SoitOutboxBacklogStalled",
        "SoitActiveRunsStuck",
    } <= names
