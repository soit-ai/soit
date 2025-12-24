""" sentry

Sentry integration.
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.kernel.config.settings import settings


def init_sentry() -> None:
    """Initialize Sentry SDK."""
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1,  # 10% of transactions
            environment="production",  # Set from env var in production
        )


# Initialize on import if DSN is configured
if settings.sentry_dsn:
    init_sentry()
