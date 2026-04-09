"""Refactor guardrails for the Agent-centered migration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    Path("server/docs/README.md"),
    Path("server/docs/architecture/README.md"),
    Path("server/docs/architecture/PROJECT_STRUCTURE.md"),
    Path("web/docs/README.md"),
    Path("web/docs/PROJECT_STRUCTURE.md"),
)

GUARDED_DIRS = (
    Path("server/app/kernel/runtime"),
    Path("server/app/modules/agent/domain"),
    Path("server/app/modules/skill"),
    Path("server/app/modules/knowledge"),
    Path("server/app/modules/plugin"),
    Path("server/app/modules/integrations/mcp"),
    Path("web/app/routes/agents"),
    Path("web/app/routes/knowledge"),
    Path("web/app/routes/tasks"),
    Path("web/app/routes/observability"),
    Path("web/app/modules/agents"),
    Path("web/app/modules/knowledge"),
    Path("web/app/modules/runs"),
)

FORBIDDEN_IMPORT_PATTERNS = (
    "from app.modules.appcenter",
    "import app.modules.appcenter",
    "from app.api.v1.appcenter",
    "import app.api.v1.appcenter",
)

RUNTIME_TERM_GUARDED_PATHS = (
    Path("server/app/api/v1/knowledge"),
    Path("server/app/modules/knowledge/application/schemas.py"),
    Path("server/tests/entrypoints/test_knowledge_api.py"),
    Path("server/tests/entrypoints/test_thread_api.py"),
    Path("web/app/components/nav/root-sidebar.tsx"),
    Path("web/app/i18n/en-US/agent.ts"),
    Path("web/app/i18n/zh-CN/agent.ts"),
    Path("web/app/routes/agents"),
    Path("web/app/routes/index"),
)

FORBIDDEN_RUNTIME_TERM_PATTERNS = (
    re.compile(r"legacy_app_ref"),
    re.compile(r"knowledge_id"),
    re.compile(r"\bcreateApp\b"),
    re.compile(r"\bnewApp\b", re.IGNORECASE),
    re.compile(r"\bdeleteApp\b"),
    re.compile(r"\bduplicateApp\b"),
    re.compile(r"\bappSelector\b"),
    re.compile(r"['\"]App['\"]"),
    re.compile(r"['\"]Application['\"]"),
    re.compile(r"['\"]Knowledge['\"]"),
    re.compile(r"应用设置"),
    re.compile(r"应用类型"),
    re.compile(r"知识库"),
)


@dataclass(frozen=True)
class GuardrailViolation:
    """Describes a single guardrail violation."""

    path: Path
    reason: str


def iter_required_file_violations(repo_root: Path = REPO_ROOT) -> list[GuardrailViolation]:
    """Return missing required-doc violations."""

    violations: list[GuardrailViolation] = []
    for relative_path in REQUIRED_FILES:
        full_path = repo_root / relative_path
        if not full_path.exists():
            violations.append(
                GuardrailViolation(relative_path, "required refactor baseline file is missing")
            )
    return violations


def iter_forbidden_import_violations(repo_root: Path = REPO_ROOT) -> list[GuardrailViolation]:
    """Return forbidden-import violations inside new architecture target directories."""

    violations: list[GuardrailViolation] = []
    for relative_dir in GUARDED_DIRS:
        full_dir = repo_root / relative_dir
        if not full_dir.exists():
            continue
        for path in full_dir.rglob("*"):
            if path.suffix not in {".py", ".ts", ".tsx", ".md"}:
                continue
            content = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_IMPORT_PATTERNS:
                if pattern in content:
                    violations.append(
                        GuardrailViolation(
                            path.relative_to(repo_root),
                            f"forbidden legacy dependency found: {pattern}",
                        )
                    )
    return violations


def iter_forbidden_runtime_term_violations(repo_root: Path = REPO_ROOT) -> list[GuardrailViolation]:
    """Return forbidden runtime vocabulary violations on already-converged surfaces."""

    violations: list[GuardrailViolation] = []
    for relative_path in RUNTIME_TERM_GUARDED_PATHS:
        full_path = repo_root / relative_path
        if not full_path.exists():
            continue

        candidates = [full_path] if full_path.is_file() else [
            path for path in full_path.rglob("*") if path.suffix in {".py", ".ts", ".tsx"}
        ]

        for path in candidates:
            content = path.read_text(encoding="utf-8")
            for pattern in FORBIDDEN_RUNTIME_TERM_PATTERNS:
                if pattern.search(content):
                    violations.append(
                        GuardrailViolation(
                            path.relative_to(repo_root),
                            f"forbidden runtime vocabulary found: {pattern.pattern}",
                        )
                    )
                    break
    return violations


def collect_guardrail_violations(repo_root: Path = REPO_ROOT) -> list[GuardrailViolation]:
    """Collect all current guardrail violations."""

    return [
        *iter_required_file_violations(repo_root),
        *iter_forbidden_import_violations(repo_root),
        *iter_forbidden_runtime_term_violations(repo_root),
    ]


def main() -> int:
    """CLI entry point."""

    violations = collect_guardrail_violations()
    if not violations:
        print("Refactor guardrails: OK")
        return 0

    print("Refactor guardrails: violations found")
    for violation in violations:
        print(f"- {violation.path}: {violation.reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
