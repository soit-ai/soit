"""Where the CLI keeps the API address and key it signed in with.

``soit login`` writes ``config.json`` under the user's configuration directory
(``SOIT_CONFIG`` names another file), readable by the user alone. The
environment wins over the file, so CI can run the CLI with no file at all:
``SOIT_API_URL``, ``SOIT_API_KEY`` and ``SOIT_WORKSPACE_ID``.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_URL = "http://localhost:9200"


@dataclass(frozen=True)
class Credentials:
    url: str
    api_key: str
    workspace_id: str | None = None


def config_path() -> Path:
    explicit = os.environ.get("SOIT_CONFIG")
    if explicit:
        return Path(explicit)
    if os.name == "nt" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"])
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "soit" / "config.json"


def _stored() -> dict[str, str]:
    path = config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise SystemExit(f"soit: cannot read {path}: {exc}") from exc
    return {key: str(value) for key, value in data.items() if value is not None} if isinstance(data, dict) else {}


def load() -> Credentials | None:
    """The credentials to use: the environment's, then the stored ones."""

    stored = _stored()
    api_key = os.environ.get("SOIT_API_KEY") or stored.get("api_key")
    if not api_key:
        return None
    return Credentials(
        url=(os.environ.get("SOIT_API_URL") or stored.get("url") or DEFAULT_URL).rstrip("/"),
        api_key=api_key,
        workspace_id=os.environ.get("SOIT_WORKSPACE_ID") or stored.get("workspace_id") or None,
    )


def save(credentials: Credentials) -> Path:
    """Write the credentials for this user only."""

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({key: value for key, value in asdict(credentials).items() if value}, indent=2)
    # Created with owner-only permissions rather than tightened afterwards, so
    # the key is never readable by others, not even briefly.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(body + "\n")
    return path


def remove() -> bool:
    """Forget the stored credentials; True when there were some."""

    try:
        config_path().unlink()
    except FileNotFoundError:
        return False
    return True
