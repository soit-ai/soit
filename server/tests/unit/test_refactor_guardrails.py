"""Tests for repository refactor guardrails."""

from pathlib import Path

from scripts.refactor_guardrails import (
    FORBIDDEN_IMPORT_PATTERNS,
    REQUIRED_FILES,
    REPO_ROOT,
    collect_guardrail_violations,
)


def test_required_refactor_files_exist() -> None:
    """Batch A0 baseline docs should exist in the repository."""

    missing = [relative for relative in REQUIRED_FILES if not (REPO_ROOT / relative).exists()]
    assert missing == []


def test_guarded_directories_do_not_import_retired_modules() -> None:
    """New architecture target directories must not take fresh dependencies on retired modules."""

    violations = collect_guardrail_violations()
    assert violations == []


def test_forbidden_import_patterns_are_legacy_specific() -> None:
    """Guardrails should only block explicit retired-module imports for now."""

    assert FORBIDDEN_IMPORT_PATTERNS == (
        "from app.modules.appcenter",
        "import app.modules.appcenter",
        "from app.api.v1.appcenter",
        "import app.api.v1.appcenter",
    )
