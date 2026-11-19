"""app.main copies server/.env into the environment unless dotenv is disabled."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app import main


def test_the_env_file_is_loaded_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SOIT_ENV_PROBE=from-file\n", encoding="utf-8")
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)
    monkeypatch.delenv("SOIT_ENV_PROBE", raising=False)

    main._load_env_file(env_file)

    assert os.environ.pop("SOIT_ENV_PROBE") == "from-file"


def test_python_dotenv_disabled_keeps_it_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SOIT_ENV_PROBE=from-file\n", encoding="utf-8")
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "true")
    monkeypatch.delenv("SOIT_ENV_PROBE", raising=False)

    main._load_env_file(env_file)

    assert "SOIT_ENV_PROBE" not in os.environ
