"""Production refuses to bootstrap an admin with the documented default password."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_admin.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bootstrap_admin", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_production_refuses_the_default_password(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    monkeypatch.setattr(module.settings, "environment", "production")
    monkeypatch.setattr(
        sys, "argv", ["bootstrap_admin.py", "--email", "a@example.com", "--password", "changeme123"]
    )

    def no_database():
        raise AssertionError("the refusal comes before any database work")

    monkeypatch.setattr(module, "get_async_session_local", no_database)

    assert await module.main() == 2
