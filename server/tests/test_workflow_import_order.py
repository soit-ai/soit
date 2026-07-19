"""Regression tests for workflow module import boundaries."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_execution_engine_imports_in_fresh_process_without_service_preload() -> None:
    server_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app.modules.workflow.runtime.engine import ExecutionEngine; "
                "assert ExecutionEngine.__name__ == 'ExecutionEngine'"
            ),
        ],
        cwd=server_root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
