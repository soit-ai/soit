"""The lite profile's combined worker runs the same loops as the dedicated scripts."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "combined_worker.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("combined_worker", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_the_combined_worker_starts_all_four_loops(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load()
    started: list[str] = []

    class Loop:
        def __init__(self, name: str) -> None:
            self.name = name
            self.worker_id = f"{name}-worker"

        async def run_loop(self, **_: object) -> None:
            started.append(self.name)

    monkeypatch.setattr(module, "setup_logging", lambda: None)
    monkeypatch.setattr(module, "configure_telemetry", lambda **_: None)
    monkeypatch.setattr(module, "start_http_server", lambda *_, **__: None)
    monkeypatch.setattr(module, "PluginRuntimeLoader", lambda: type("L", (), {"load_all": lambda self: None})())
    monkeypatch.setattr(module, "OutboxDispatcherService", lambda *_, **__: Loop("outbox"))
    monkeypatch.setattr(module, "OutboxRetentionService", lambda *_, **__: Loop("retention"))
    monkeypatch.setattr(module, "GlobalKnowledgeIngestWorker", lambda: Loop("ingest"))
    monkeypatch.setattr(module, "ScheduleWorker", lambda *_, **__: Loop("schedule"))

    await asyncio.wait_for(module.main(), timeout=5)

    assert sorted(started) == ["ingest", "outbox", "retention", "schedule"]
