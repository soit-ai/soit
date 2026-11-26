"""Every directory of application code is a regular package.

import-linter builds its graph from packages, so a directory without an
``__init__.py`` drops out of every contract silently. One such directory
hid an API module importing a domain model.
"""

from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2] / "app"


def test_every_python_directory_has_a_package_marker() -> None:
    missing = sorted(
        str(directory.relative_to(APP_ROOT.parent))
        for directory in [APP_ROOT, *APP_ROOT.rglob("*")]
        if directory.is_dir()
        and directory.name != "__pycache__"
        and any(directory.glob("*.py"))
        and not (directory / "__init__.py").exists()
    )

    assert missing == []
