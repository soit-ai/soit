"""Tests for production container and compose runtime assets."""

import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_backend_image_uses_single_uvicorn_process() -> None:
    dockerfile = (ROOT / "server" / "Dockerfile").read_text(encoding="utf-8")

    assert 'CMD ["uvicorn", "app.main:app"' in dockerfile
    assert "gunicorn" not in dockerfile.lower()
    assert "uv sync --frozen --no-dev" in dockerfile


def test_base_api_dependencies_exclude_test_and_local_training_stacks() -> None:
    project = tomllib.loads(
        (ROOT / "server" / "pyproject.toml").read_text(encoding="utf-8")
    )
    base = "\n".join(project["project"]["dependencies"]).lower()
    local_embedding = "\n".join(
        project["project"]["optional-dependencies"]["local-embedding"]
    ).lower()

    for package in ("pytest", "mypy", "pip-audit", "torch", "transformers"):
        assert package not in base
    assert "torch" in local_embedding
    assert "sentence-transformers" in local_embedding


def test_compose_defaults_to_explicit_development_and_redis_events() -> None:
    compose = yaml.safe_load(
        (ROOT / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    )

    for service_name in ("api", "knowledge-ingest-worker"):
        environment = compose["services"][service_name]["environment"]
        assert environment["ENVIRONMENT"] == "${ENVIRONMENT:-development}"
        assert environment["EVENT_BUS_BACKEND"] == "${EVENT_BUS_BACKEND:-redis}"
        assert environment["EVENT_BUS_REDIS_URL"] == (
            "${EVENT_BUS_REDIS_URL:-redis://redis:6379/0}"
        )


def test_environment_examples_declare_runtime_profile_and_event_backend() -> None:
    for path in (ROOT / ".env.example", ROOT / "server" / ".env.example"):
        content = path.read_text(encoding="utf-8")
        assert "ENVIRONMENT=development" in content
        assert "EVENT_BUS_BACKEND=redis" in content
        assert "OTEL_ENABLED=false" in content


def test_quality_workflow_builds_and_smoke_tests_backend_image() -> None:
    workflow = (ROOT / ".github" / "workflows" / "quality.yml").read_text(
        encoding="utf-8"
    )

    assert "container-smoke:" in workflow
    assert "docker compose -f docker/docker-compose.yml config --quiet" in workflow
    assert "docker build --tag soit-api:ci ./server" in workflow
    assert "/health/ready" in workflow
    assert "ENVIRONMENT: test" in workflow


def test_quality_gate_documents_blocking_container_validation() -> None:
    quality_gate = (ROOT / "docs" / "QUALITY_GATE.md").read_text(encoding="utf-8")

    assert "## Blocking Container Gate" in quality_gate
    assert "Out-Of-Scope Docker Validation" not in quality_gate
