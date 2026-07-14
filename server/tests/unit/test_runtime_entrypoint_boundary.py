"""Community runtime entrypoint boundary tests."""

from __future__ import annotations

from pathlib import Path


def test_community_main_does_not_mount_enterprise_runtime() -> None:
    main_source = Path("app/main.py").read_text(encoding="utf-8")

    assert "app.wiring.enterprise" not in main_source
    assert "mount_enterprise_extension" not in main_source
    assert "soit_enterprise" not in main_source
