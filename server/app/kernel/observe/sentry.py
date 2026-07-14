"""sentry

Sentry integration.

This integration is optional: if `sentry-sdk` isn't installed, Sentry setup is a no-op.
"""

from __future__ import annotations

try:
    import sentry_sdk  # type: ignore
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware  # type: ignore
except Exception:  # pragma: no cover
    sentry_sdk = None
    SentryAsgiMiddleware = None

from app.settings.settings import settings


def setup_sentry() -> None:
    """Initialize Sentry if enabled and dependency is available."""
    if sentry_sdk is None:
        return

    dsn: str | None = getattr(settings, "sentry_dsn", None)
    enabled: bool = bool(getattr(settings, "sentry_enabled", False) or bool(dsn))
    if not enabled:
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=getattr(settings, "env", "dev"),
        traces_sample_rate=float(getattr(settings, "sentry_traces_sample_rate", 0.0) or 0.0),
    )


def wrap_asgi(app):
    """Wrap ASGI app with Sentry middleware if available."""
    if SentryAsgiMiddleware is None:
        return app
    return SentryAsgiMiddleware(app)
