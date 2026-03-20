"""Refactor guardrails for the Agent-centered migration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    Path("app/docs/README.md"),
    Path("docs/architecture/soit-refactor-principles.md"),
    Path("docs/architecture/soit-object-mapping.md"),
    Path("docs/architecture/soit-phase-checklist.md"),
)

GUARDED_DIRS = (
    Path("app/app/kernel/runtime"),
    Path("app/app/modules/agent/domain"),
    Path("app/app/modules/skill"),
    Path("app/app/modules/knowledge"),
    Path("app/app/modules/plugin"),
    Path("app/app/modules/integrations/mcp"),
    Path("web/src/pages/agents"),
    Path("web/src/pages/knowledge"),
    Path("web/src/pages/tasks"),
    Path("web/src/pages/observability"),
    Path("web/src/modules/agents"),
    Path("web/src/modules/knowledge"),
    Path("web/src/modules/runs"),
)

FORBIDDEN_IMPORT_PATTERNS = (
    "from app.modules.appcenter",
    "import app.modules.appcenter",
    "from app.api.v1.appcenter",
    "import app.api.v1.appcenter",
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


def collect_guardrail_violations(repo_root: Path = REPO_ROOT) -> list[GuardrailViolation]:
    """Collect all current guardrail violations."""

    return [
        *iter_required_file_violations(repo_root),
        *iter_forbidden_import_violations(repo_root),
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
