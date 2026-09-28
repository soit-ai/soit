"""Mount installed extension packages into the Community application.

An extension package, such as SOIT Enterprise, declares a ``soit.extensions``
entry point naming a callable ``mount(app, settings)``. It is called once,
after Community's own routes are registered and the edition is resolved, so
it can add routes and register providers, and read the entitlements the
license granted. A package that fails to mount is logged and reported in
diagnostics; the rest of the application still starts.
"""

from __future__ import annotations

import logging
from typing import Any

from app.kernel.entitlements.edition import ExtensionMount

logger = logging.getLogger(__name__)

EXTENSION_GROUP = "soit.extensions"


def mount_extensions(app: Any, settings: Any) -> tuple[ExtensionMount, ...]:
    from importlib.metadata import entry_points

    mounts: list[ExtensionMount] = []
    for entry in entry_points(group=EXTENSION_GROUP):
        try:
            entry.load()(app, settings)
        except Exception as exc:
            logger.exception("Extension %s could not be mounted", entry.name)
            mounts.append(ExtensionMount(entry.name, "failed", f"{type(exc).__name__}: {exc}"))
            continue
        logger.info("Extension %s mounted", entry.name)
        mounts.append(ExtensionMount(entry.name, "mounted"))
    return tuple(mounts)
