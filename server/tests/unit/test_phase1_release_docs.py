"""Phase 1 release documentation artifact checks."""

from __future__ import annotations

import json
import re
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
QUICKSTART_SERVICES = {
    "postgres",
    "redis",
    "minio",
    "etcd",
    "milvus",
    "vault",
    "migrate",
    "bootstrap",
    "api",
    "web",
    "knowledge-ingest-worker",
    "outbox-dispatcher",
}
LOCAL_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
FORBIDDEN_OPEN_SOURCE_DOC_TERMS = [
    "soit-" + "local-dev",
    "SOIT_1.5_" + "Architecture_Gap_Review",
    "SOIT_1.0_" + "Owner_UI_Spotcheck",
    "." + "local" + ".json",
    "docs/" + "archive",
    "superpowers/" + "plans",
    "superpowers/" + "specs",
]


def _markdown_files() -> list[Path]:
    ignored_parts = {"node_modules", ".venv", "dist", "build"}
    return [
        path
        for path in ROOT.rglob("*.md")
        if not (set(path.relative_to(ROOT).parts) & ignored_parts)
    ]


def test_open_source_documentation_entrypoints_and_links_are_self_contained() -> None:
    for required_file in [
        ROOT / "LICENSE",
        ROOT / "CONTRIBUTING.md",
        ROOT / "docs" / "development.md",
    ]:
        assert required_file.is_file()

    broken_links: list[str] = []
    for markdown_file in _markdown_files():
        content = markdown_file.read_text(encoding="utf-8")
        for match in LOCAL_MARKDOWN_LINK_RE.finditer(content):
            target = match.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_without_anchor = target.split("#", 1)[0]
            if not target_without_anchor:
                continue
            if target_without_anchor.startswith("<") and target_without_anchor.endswith(">"):
                target_without_anchor = target_without_anchor[1:-1]
            resolved = (markdown_file.parent / target_without_anchor).resolve()
            if not resolved.exists():
                broken_links.append(f"{markdown_file.relative_to(ROOT)} -> {target}")

    assert broken_links == []


def test_open_source_docs_do_not_depend_on_local_dev_workspace() -> None:
    searchable_files = [
        *ROOT.glob("*.md"),
        *ROOT.glob("docs/**/*.md"),
        *ROOT.glob("docs/**/*.json"),
        *ROOT.glob("server/docs/**/*.md"),
        *ROOT.glob("server/tests/unit/test_phase*_release_docs.py"),
    ]
    offenders: list[str] = []
    for path in searchable_files:
        content = path.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_OPEN_SOURCE_DOC_TERMS:
            if forbidden in content:
                offenders.append(f"{path.relative_to(ROOT)} contains {forbidden}")

    assert offenders == []


def test_bilingual_quickstart_documents_cover_demo_path() -> None:
    english = ROOT / "docs" / "quickstart.md"
    chinese = ROOT / "docs" / "quickstart.zh-CN.md"

    assert english.is_file()
    assert chinese.is_file()
    assert (ROOT / "docs" / "assets" / "hero.png").is_file()

    required_terms = [
        "docker compose -f docker/docker-compose.yml up -d postgres redis minio etcd milvus vault migrate bootstrap api web knowledge-ingest-worker outbox-dispatcher",
        "bootstrap_enterprise_mvp.py",
        "tests/integration/test_enterprise_agent_mvp.py",
        "scripts/evaluate_support_ticket_regression.py",
        "http://localhost:5000",
        "http://localhost:9200",
        "curl http://localhost:9200/health/ready",
        "docs/assets/hero.png",
    ]
    for document in (english, chinese):
        content = document.read_text(encoding="utf-8")
        for term in required_terms:
            assert term in content


def test_quickstart_compose_file_matches_documented_service_set() -> None:
    compose_file = ROOT / "docker" / "docker-compose.yml"

    assert compose_file.is_file()

    compose = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    services = compose["services"]

    assert QUICKSTART_SERVICES.issubset(services)
    assert services["api"]["build"]["context"] == "../server"
    assert services["api"]["command"] == [
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "9200",
    ]
    assert services["web"]["build"]["context"] == "../web"
    assert services["web"]["healthcheck"]["test"] == [
        "CMD-SHELL",
        "wget -q -O - http://127.0.0.1:5000/ > /dev/null 2>&1",
    ]
    assert services["migrate"]["command"] == ["sh", "scripts/migrate.sh"]
    assert services["knowledge-ingest-worker"]["command"] == [
        "python",
        "scripts/ingest_worker.py",
    ]
    assert services["etcd"]["healthcheck"]["test"] == [
        "CMD",
        "etcdctl",
        "--endpoints=http://localhost:2379",
        "endpoint",
        "health",
    ]
    assert services["minio"]["healthcheck"]["test"] == [
        "CMD",
        "curl",
        "-f",
        "http://localhost:9000/minio/health/live",
    ]
    assert services["minio-init"]["entrypoint"] == ["/bin/sh", "-ec"]
    assert len(services["minio-init"]["command"]) == 1
    assert "until mc alias set local http://minio:9000" in services["minio-init"]["command"][0]
    assert services["milvus"]["environment"]["MINIO_ACCESS_KEY_ID"] == "${MINIO_ACCESS_KEY:-soitminio}"
    assert services["milvus"]["environment"]["MINIO_SECRET_ACCESS_KEY"] == "${MINIO_SECRET_KEY:-soitminio}"
    assert services["milvus"]["healthcheck"]["test"] == [
        "CMD",
        "curl",
        "-f",
        "http://localhost:9091/healthz",
    ]
    # The dedicated worker must drain the queue continuously. A positive limit
    # here made the container exit and restart after every few documents.
    assert (
        services["knowledge-ingest-worker"]["environment"]["KNOWLEDGE_INGEST_WORKER_MAX_TASKS"]
        == "${KNOWLEDGE_INGEST_WORKER_MAX_TASKS:-0}"
    )
    for service_name in ("migrate", "bootstrap", "api", "knowledge-ingest-worker", "outbox-dispatcher"):
        env_files = services[service_name]["env_file"]
        assert env_files == [{"path": "../.env", "required": False}]

    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "KNOWLEDGE_INGEST_WORKER_MAX_TASKS=0" in env_example


def test_readmes_link_bilingual_quickstart() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_cn = (ROOT / "README-cn.md").read_text(encoding="utf-8")

    assert "docs/quickstart.md" in readme
    assert "docs/quickstart.zh-CN.md" in readme_cn


def test_web_docker_runtime_serves_spa_build_output() -> None:
    package = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    dockerfile = (ROOT / "web" / "Dockerfile").read_text(encoding="utf-8")

    assert package["scripts"]["start"] == "node ./scripts/serve-client.mjs"
    assert "COPY scripts/serve-client.mjs ./scripts/serve-client.mjs" in dockerfile


def test_scripts_readme_documents_phase1_demo_seed() -> None:
    content = (ROOT / "server" / "scripts" / "README.md").read_text(encoding="utf-8")
    required_terms = [
        "bootstrap_enterprise_mvp.py",
        "seed_enterprise_mvp_scenarios.py",
        "sample Provider",
        "sample Knowledge",
        "sample Agent",
        "sample Workflow",
        "idempotent",
    ]
    for term in required_terms:
        assert term in content


def test_phase1_migration_runbook_documents_fresh_install_and_n1_upgrade() -> None:
    runbook = ROOT / "docs" / "release-migration.md"

    assert runbook.is_file()

    content = runbook.read_text(encoding="utf-8")
    required_terms = [
        "SOIT 1.0 Migration Runbook",
        "Supported Paths",
        "Fresh Installation",
        "N-1 Upgrade",
        "20260718140000",
        "20260723160000",
        "20260728200000",
        "uv run alembic heads",
        "uv run alembic upgrade head",
        "uv run alembic current",
        "Exit Evidence",
    ]
    for term in required_terms:
        assert term in content
    assert "single Alembic baseline" not in content


def test_phase1_migration_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_release_migration_paths import (
        MigrationEvidenceError,
        load_evidence,
        validate_migration_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "release-migration-evidence.example.json"
    )

    report = validate_migration_evidence(evidence)

    assert report["passed"] is True
    assert report["head_revision"] == "20260728200000"
    assert report["paths"] == {
        "fresh_install": "20260728200000",
        "n1_upgrade": "20260718140000..20260728200000",
    }

    broken = deepcopy(evidence)
    broken["fresh_install"] = {
        **evidence["fresh_install"],
        "post_upgrade_revision": "wrong_revision",
    }
    with pytest.raises(MigrationEvidenceError, match="fresh_install"):
        validate_migration_evidence(broken)

    wrong_feature = dict(evidence)
    wrong_feature["featureKey"] = "phase1.wrong_migration"
    with pytest.raises(MigrationEvidenceError, match="featureKey"):
        validate_migration_evidence(wrong_feature)

    broken_n1 = deepcopy(evidence)
    broken_n1["n1_upgrade"]["source_revision"] = "wrong_revision"
    with pytest.raises(MigrationEvidenceError, match="n1_upgrade"):
        validate_migration_evidence(broken_n1)

    invalid_window = dict(evidence)
    invalid_window["finishedAt"] = "2026-06-11T09:59:59Z"
    with pytest.raises(MigrationEvidenceError, match="finishedAt"):
        validate_migration_evidence(invalid_window)


def test_model_provider_support_matrix_documents_phase1_acceptance_scope() -> None:
    matrix = ROOT / "docs" / "model-provider-support.md"

    assert matrix.is_file()

    content = matrix.read_text(encoding="utf-8")
    required_terms = [
        "SOIT 1.0 Model Provider Support Matrix",
        "OpenAI",
        "OpenAI-compatible",
        "DeepSeek",
        "Anthropic",
        "Gemini",
        "Runtime adapter",
        "ModelHub diagnostics",
        "Phase 1 acceptance",
        "tests/unit/test_modelhub_provider_catalog.py",
        "tests/unit/test_openai_tool_calling.py",
        "tests/unit/test_deepseek_llm_port.py",
        "tests/unit/test_anthropic_llm_port.py",
    ]
    for term in required_terms:
        assert term in content


def test_phase1_manual_acceptance_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_phase1_manual_acceptance import (
        ManualAcceptanceEvidenceError,
        load_evidence,
        validate_manual_acceptance_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-manual-acceptance-evidence.example.json"
    )

    report = validate_manual_acceptance_evidence(evidence)

    assert report["passed"] is True
    assert report["route_count"] == 9
    assert report["chains"] == ["chain_a", "chain_b"]
    route_paths = {route["path"] for route in evidence["owner_ui_spotcheck"]["routeResults"]}
    assert "/observe/runs" in route_paths
    assert "/runs" not in route_paths

    broken = dict(evidence)
    broken["owner_ui_spotcheck"] = {
        **evidence["owner_ui_spotcheck"],
        "result": "Needs follow-up",
    }
    with pytest.raises(ManualAcceptanceEvidenceError, match="owner_ui_spotcheck"):
        validate_manual_acceptance_evidence(broken)

    missing_mobile_viewport = dict(evidence)
    missing_mobile_viewport["owner_ui_spotcheck"] = {
        **evidence["owner_ui_spotcheck"],
        "routeResults": [
            {
                **route,
                "viewports": [
                    viewport
                    for viewport in [
                        {
                            "name": "desktop",
                            "status": "passed",
                            "evidenceRef": f"{route['evidenceRef']}.desktop.png",
                        },
                        {
                            "name": "mobile",
                            "status": "passed",
                            "evidenceRef": f"{route['evidenceRef']}.mobile.png",
                        },
                    ]
                    if viewport["name"] != "mobile"
                ],
            }
            if route["path"] == "/chat"
            else route
            for route in evidence["owner_ui_spotcheck"]["routeResults"]
        ],
    }
    with pytest.raises(ManualAcceptanceEvidenceError, match="/chat.*mobile"):
        validate_manual_acceptance_evidence(missing_mobile_viewport)

    duplicate_route = dict(evidence)
    duplicate_route["owner_ui_spotcheck"] = {
        **evidence["owner_ui_spotcheck"],
        "routeResults": [
            *evidence["owner_ui_spotcheck"]["routeResults"],
            evidence["owner_ui_spotcheck"]["routeResults"][0],
        ],
    }
    with pytest.raises(ManualAcceptanceEvidenceError, match="duplicate route"):
        validate_manual_acceptance_evidence(duplicate_route)

    duplicate_viewport = dict(evidence)
    duplicate_viewport["owner_ui_spotcheck"] = {
        **evidence["owner_ui_spotcheck"],
        "routeResults": [
            {
                **route,
                "viewports": [*route["viewports"], route["viewports"][0]],
            }
            if route["path"] == "/chat"
            else route
            for route in evidence["owner_ui_spotcheck"]["routeResults"]
        ],
    }
    with pytest.raises(ManualAcceptanceEvidenceError, match="duplicate viewport"):
        validate_manual_acceptance_evidence(duplicate_viewport)

    duplicate_chain = dict(evidence)
    duplicate_chain["chainResults"] = [*evidence["chainResults"], evidence["chainResults"][0]]
    with pytest.raises(ManualAcceptanceEvidenceError, match="duplicate chain"):
        validate_manual_acceptance_evidence(duplicate_chain)

    duplicate_route_evidence = deepcopy(evidence)
    duplicate_route_evidence["owner_ui_spotcheck"]["routeResults"][1]["evidenceRef"] = (
        duplicate_route_evidence["owner_ui_spotcheck"]["routeResults"][0]["evidenceRef"]
    )
    with pytest.raises(ManualAcceptanceEvidenceError, match="duplicate evidenceRef"):
        validate_manual_acceptance_evidence(duplicate_route_evidence)

    duplicate_viewport_evidence = deepcopy(evidence)
    duplicate_viewport_evidence["owner_ui_spotcheck"]["routeResults"][0]["viewports"][1]["evidenceRef"] = (
        duplicate_viewport_evidence["owner_ui_spotcheck"]["routeResults"][0]["viewports"][0]["evidenceRef"]
    )
    with pytest.raises(ManualAcceptanceEvidenceError, match="duplicate evidenceRef"):
        validate_manual_acceptance_evidence(duplicate_viewport_evidence)

    duplicate_chain_evidence = deepcopy(evidence)
    duplicate_chain_evidence["chainResults"][1]["evidenceRef"] = duplicate_chain_evidence["chainResults"][0][
        "evidenceRef"
    ]
    with pytest.raises(ManualAcceptanceEvidenceError, match="duplicate evidenceRef"):
        validate_manual_acceptance_evidence(duplicate_chain_evidence)

    invalid_window = dict(evidence)
    invalid_window["finishedAt"] = "2026-06-11T06:59:59Z"
    with pytest.raises(ManualAcceptanceEvidenceError, match="finishedAt"):
        validate_manual_acceptance_evidence(invalid_window)


def test_phase1_manual_acceptance_strict_mode_requires_existing_evidence_refs(tmp_path: Path) -> None:
    from scripts.verify_phase1_manual_acceptance import (
        ManualAcceptanceEvidenceError,
        load_evidence,
        validate_manual_acceptance_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-manual-acceptance-evidence.example.json"
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    refs = [evidence["owner_ui_spotcheck"]["signedRecordRef"]]
    for route in evidence["owner_ui_spotcheck"]["routeResults"]:
        refs.append(route["evidenceRef"])
        refs.extend(viewport["evidenceRef"] for viewport in route["viewports"])
    refs.extend(chain["evidenceRef"] for chain in evidence["chainResults"])
    for evidence_ref in refs:
        path = repo_root / evidence_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{evidence_ref}\n", encoding="utf-8")

    report = validate_manual_acceptance_evidence(evidence, repo_root=repo_root)

    assert report["passed"] is True

    (repo_root / refs[0]).unlink()
    with pytest.raises(ManualAcceptanceEvidenceError, match="evidenceRef does not exist"):
        validate_manual_acceptance_evidence(evidence, repo_root=repo_root)


def test_model_provider_spotcheck_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_model_provider_spotcheck import (
        ModelProviderSpotcheckEvidenceError,
        load_evidence,
        validate_model_provider_spotcheck,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "model-provider-spotcheck-evidence.example.json"
    )

    report = validate_model_provider_spotcheck(evidence)

    assert report["passed"] is True
    assert report["provider_count"] == 2
    assert report["providers"] == ["anthropic", "openai"]

    broken = dict(evidence)
    broken["providers"] = [evidence["providers"][0]]
    with pytest.raises(ModelProviderSpotcheckEvidenceError, match="at least 2"):
        validate_model_provider_spotcheck(broken)

    duplicate_provider = dict(evidence)
    duplicate_provider["providers"] = [*evidence["providers"], evidence["providers"][0]]
    with pytest.raises(ModelProviderSpotcheckEvidenceError, match="duplicate provider"):
        validate_model_provider_spotcheck(duplicate_provider)

    duplicate_provider_evidence = deepcopy(evidence)
    duplicate_provider_evidence["providers"][0]["chatCompletionEvidenceRef"] = duplicate_provider_evidence[
        "providers"
    ][0]["diagnosticsEvidenceRef"]
    with pytest.raises(ModelProviderSpotcheckEvidenceError, match="duplicate evidenceRef"):
        validate_model_provider_spotcheck(duplicate_provider_evidence)

    invalid_window = dict(evidence)
    invalid_window["finishedAt"] = "2026-06-11T07:59:59Z"
    with pytest.raises(ModelProviderSpotcheckEvidenceError, match="finishedAt"):
        validate_model_provider_spotcheck(invalid_window)


def test_model_provider_spotcheck_strict_mode_requires_existing_evidence_refs(tmp_path: Path) -> None:
    from scripts.verify_model_provider_spotcheck import (
        ModelProviderSpotcheckEvidenceError,
        load_evidence,
        validate_model_provider_spotcheck,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "model-provider-spotcheck-evidence.example.json"
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    refs = [
        provider[field]
        for provider in evidence["providers"]
        for field in (
            "diagnosticsEvidenceRef",
            "chatCompletionEvidenceRef",
            "costAttributionEvidenceRef",
        )
    ]
    for evidence_ref in refs:
        path = repo_root / evidence_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{evidence_ref}\n", encoding="utf-8")

    report = validate_model_provider_spotcheck(evidence, repo_root=repo_root)

    assert report["passed"] is True

    (repo_root / refs[0]).unlink()
    with pytest.raises(ModelProviderSpotcheckEvidenceError, match="evidenceRef does not exist"):
        validate_model_provider_spotcheck(evidence, repo_root=repo_root)


def test_quickstart_deployment_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_quickstart_deployment import (
        QuickstartDeploymentEvidenceError,
        load_evidence,
        validate_quickstart_deployment,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "quickstart-deployment-evidence.example.json"
    )

    report = validate_quickstart_deployment(evidence)

    assert report["passed"] is True
    assert report["elapsed_seconds"] == 540
    assert report["chain_a"] == "passed"

    broken = dict(evidence)
    broken["docker"] = {
        **evidence["docker"],
        "elapsedSeconds": 601,
    }
    with pytest.raises(QuickstartDeploymentEvidenceError, match="10 minutes"):
        validate_quickstart_deployment(broken)

    missing_service_evidence = dict(evidence)
    missing_service_evidence["docker"] = {
        **evidence["docker"],
        "services": [
            {
                key: value
                for key, value in service.items()
                if key != "evidenceRef"
            }
            if service["name"] == "api"
            else service
            for service in evidence["docker"]["services"]
        ],
    }
    with pytest.raises(QuickstartDeploymentEvidenceError, match="docker.services.api.evidenceRef"):
        validate_quickstart_deployment(missing_service_evidence)

    unhealthy_service = dict(evidence)
    unhealthy_service["docker"] = {
        **evidence["docker"],
        "services": [
            {
                **service,
                "health": "unhealthy",
            }
            if service["name"] == "api"
            else service
            for service in evidence["docker"]["services"]
        ],
    }
    with pytest.raises(QuickstartDeploymentEvidenceError, match="docker.services.api.health"):
        validate_quickstart_deployment(unhealthy_service)

    duplicate_service = dict(evidence)
    duplicate_service["docker"] = {
        **evidence["docker"],
        "services": [*evidence["docker"]["services"], evidence["docker"]["services"][0]],
    }
    with pytest.raises(QuickstartDeploymentEvidenceError, match="duplicate docker service"):
        validate_quickstart_deployment(duplicate_service)

    duplicate_service_evidence = deepcopy(evidence)
    duplicate_service_evidence["docker"]["services"][1]["evidenceRef"] = duplicate_service_evidence["docker"][
        "services"
    ][0]["evidenceRef"]
    with pytest.raises(QuickstartDeploymentEvidenceError, match="duplicate evidenceRef"):
        validate_quickstart_deployment(duplicate_service_evidence)

    duplicate_check_evidence = deepcopy(evidence)
    duplicate_check_evidence["checks"]["webHealth"]["evidenceRef"] = duplicate_check_evidence["checks"][
        "apiHealth"
    ]["evidenceRef"]
    with pytest.raises(QuickstartDeploymentEvidenceError, match="duplicate evidenceRef"):
        validate_quickstart_deployment(duplicate_check_evidence)

    invalid_window = dict(evidence)
    invalid_window["finishedAt"] = "2026-06-11T08:59:59Z"
    with pytest.raises(QuickstartDeploymentEvidenceError, match="finishedAt"):
        validate_quickstart_deployment(invalid_window)

    init_still_running = deepcopy(evidence)
    for service in init_still_running["docker"]["services"]:
        if service["name"] == "migrate":
            service["status"] = "running"
            service.pop("exitCode", None)
    with pytest.raises(QuickstartDeploymentEvidenceError, match="one-shot init container"):
        validate_quickstart_deployment(init_still_running)

    init_nonzero_exit = deepcopy(evidence)
    for service in init_nonzero_exit["docker"]["services"]:
        if service["name"] == "bootstrap":
            service["exitCode"] = 1
    with pytest.raises(QuickstartDeploymentEvidenceError, match="bootstrap.exitCode must be 0"):
        validate_quickstart_deployment(init_nonzero_exit)


def test_quickstart_deployment_strict_mode_requires_existing_evidence_refs(tmp_path: Path) -> None:
    from scripts.verify_quickstart_deployment import (
        QuickstartDeploymentEvidenceError,
        load_evidence,
        validate_quickstart_deployment,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "quickstart-deployment-evidence.example.json"
    )

    with pytest.raises(QuickstartDeploymentEvidenceError, match="evidenceRef does not exist"):
        validate_quickstart_deployment(evidence, repo_root=tmp_path)


def test_phase1_non_developer_feedback_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_phase1_user_feedback import (
        UserFeedbackEvidenceError,
        load_evidence,
        validate_user_feedback_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-user-feedback-evidence.example.json"
    )

    report = validate_user_feedback_evidence(evidence)

    assert report["passed"] is True
    assert report["participant_count"] == 2
    assert report["completed_chain"] == "chain_a"

    broken = dict(evidence)
    broken["participants"] = [
        {
            **participant,
            "role": "developer",
        }
        for participant in evidence["participants"]
    ]
    with pytest.raises(UserFeedbackEvidenceError, match="non-developer"):
        validate_user_feedback_evidence(broken)

    duplicate_participant = dict(evidence)
    duplicate_participant["participants"] = [
        evidence["participants"][0],
        {
            **evidence["participants"][1],
            "userRef": evidence["participants"][0]["userRef"],
        },
    ]
    with pytest.raises(UserFeedbackEvidenceError, match="unique"):
        validate_user_feedback_evidence(duplicate_participant)

    invalid_window = dict(evidence)
    invalid_window["finishedAt"] = "2026-06-11T07:59:59Z"
    with pytest.raises(UserFeedbackEvidenceError, match="finishedAt"):
        validate_user_feedback_evidence(invalid_window)

    participant_outside_window = dict(evidence)
    participant_outside_window["participants"] = [
        {
            **evidence["participants"][0],
            "completedAt": "2026-06-11T08:46:00Z",
        },
        evidence["participants"][1],
    ]
    with pytest.raises(UserFeedbackEvidenceError, match="completedAt"):
        validate_user_feedback_evidence(participant_outside_window)


def test_phase1_non_developer_feedback_strict_mode_requires_existing_evidence_refs(tmp_path: Path) -> None:
    from scripts.verify_phase1_user_feedback import (
        UserFeedbackEvidenceError,
        load_evidence,
        validate_user_feedback_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-user-feedback-evidence.example.json"
    )
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    refs = [participant["feedbackRef"] for participant in evidence["participants"]]
    refs.extend(
        [
            evidence["releaseDecision"]["decisionRef"],
            evidence["releaseDecision"]["knownLimitationsRef"],
        ]
    )
    for evidence_ref in refs:
        path = repo_root / evidence_ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{evidence_ref}\n", encoding="utf-8")

    report = validate_user_feedback_evidence(evidence, repo_root=repo_root)

    assert report["passed"] is True

    (repo_root / refs[0]).unlink()
    with pytest.raises(UserFeedbackEvidenceError, match="evidenceRef does not exist"):
        validate_user_feedback_evidence(evidence, repo_root=repo_root)


def test_phase1_release_evidence_template_is_machine_verifiable() -> None:
    from scripts.verify_phase1_release import (
        Phase1ReleaseEvidenceError,
        load_evidence,
        validate_phase1_release_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-release-v1.0.0-evidence.example.json"
    )

    report = validate_phase1_release_evidence(evidence)

    assert report["passed"] is True
    assert report["release"] == "v1.0.0"
    assert report["release_tag"] == "v1.0.0"

    broken = dict(evidence)
    broken["clean_worktree_at_tag"] = False
    with pytest.raises(Phase1ReleaseEvidenceError, match="clean_worktree_at_tag"):
        validate_phase1_release_evidence(broken)

    broken_commit = dict(evidence)
    broken_commit["commit"] = "not-a-release-commit"
    with pytest.raises(Phase1ReleaseEvidenceError, match="commit"):
        validate_phase1_release_evidence(broken_commit)

    zero_commit = dict(evidence)
    zero_commit["commit"] = "0000000000000000000000000000000000000000"
    with pytest.raises(Phase1ReleaseEvidenceError, match="commit"):
        validate_phase1_release_evidence(zero_commit)

    invalid_published_at = dict(evidence)
    invalid_published_at["publishedAt"] = "not-a-timestamp"
    with pytest.raises(Phase1ReleaseEvidenceError, match="publishedAt"):
        validate_phase1_release_evidence(invalid_published_at)

    duplicate_evidence_ref = deepcopy(evidence)
    duplicate_evidence_ref["evidence"][1]["evidenceRef"] = duplicate_evidence_ref["evidence"][0]["evidenceRef"]
    with pytest.raises(Phase1ReleaseEvidenceError, match="duplicate evidenceRef"):
        validate_phase1_release_evidence(duplicate_evidence_ref)


def test_phase1_release_evidence_requires_non_developer_feedback() -> None:
    from scripts.verify_phase1_release import (
        Phase1ReleaseEvidenceError,
        load_evidence,
        validate_phase1_release_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-release-v1.0.0-evidence.example.json"
    )
    evidence["evidence"] = [
        record
        for record in evidence["evidence"]
        if record["name"] != "non_developer_feedback"
    ]

    with pytest.raises(Phase1ReleaseEvidenceError, match="non_developer_feedback"):
        validate_phase1_release_evidence(evidence)


def test_phase1_release_evidence_requires_unique_evidence_names() -> None:
    from scripts.verify_phase1_release import (
        Phase1ReleaseEvidenceError,
        load_evidence,
        validate_phase1_release_evidence,
    )

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-release-v1.0.0-evidence.example.json"
    )
    evidence["evidence"].append(evidence["evidence"][0])

    with pytest.raises(Phase1ReleaseEvidenceError, match="duplicate evidence"):
        validate_phase1_release_evidence(evidence)


def test_phase1_release_evidence_strict_mode_verifies_tag_and_local_refs(tmp_path: Path) -> None:
    from scripts.verify_phase1_release import (
        Phase1ReleaseEvidenceError,
        load_evidence,
        validate_phase1_release_evidence,
    )

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "release@example.test"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Release Test"], cwd=repo_root, check=True)

    release_notes = repo_root / "docs" / "releases" / "v1.0.0.md"
    release_notes.parent.mkdir(parents=True)
    release_notes.write_text("# v1.0.0\n", encoding="utf-8")

    evidence = load_evidence(
        ROOT / "docs" / "deployment" / "phase1-release-v1.0.0-evidence.example.json"
    )
    for record in evidence["evidence"]:
        evidence_ref = repo_root / record["evidenceRef"]
        evidence_ref.parent.mkdir(parents=True, exist_ok=True)
        evidence_ref.write_text(f"{record['name']} evidence\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo_root, check=True)
    subprocess.run(["git", "commit", "-m", "release evidence"], cwd=repo_root, check=True, capture_output=True, text=True)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "tag", "v1.0.0", commit], cwd=repo_root, check=True)
    evidence["commit"] = commit

    report = validate_phase1_release_evidence(evidence, repo_root=repo_root)

    assert report["passed"] is True

    broken = deepcopy(evidence)
    broken["commit"] = "0123456789abcdef0123456789abcdef01234567"
    with pytest.raises(Phase1ReleaseEvidenceError, match="release_tag"):
        validate_phase1_release_evidence(broken, repo_root=repo_root)

    missing_ref = deepcopy(evidence)
    (repo_root / missing_ref["evidence"][0]["evidenceRef"]).unlink()
    with pytest.raises(Phase1ReleaseEvidenceError, match="evidenceRef does not exist"):
        validate_phase1_release_evidence(missing_ref, repo_root=repo_root)
