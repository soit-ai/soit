"""Resolve the edition from the license file and keep checking it while running.

Community needs no license. With ``ENTERPRISE_LICENSE_PATH`` set, the license
decides: a verified, unexpired one makes the process Enterprise with its
feature keys, anything else leaves it Community and says why. The feature
keys a license grants are checked against the registries installed extension
packages declare; a key none defines is ignored and reported, not fatal.

While a license is configured, a daily heartbeat logs its state with the
deployment's month-to-date metering (metered calls, active principals and
API keys), and drops the process to Community if the license lapses.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import distinct, func, select

from app.kernel.entitlements.edition import (
    EditionState,
    ExtensionMount,
    current_edition,
    set_current_edition,
)
from app.kernel.entitlements.features import (
    FeatureRegistry,
    extension_feature_files,
    resolve_enabled_features,
)
from app.kernel.entitlements.license import LicenseState, LicenseStatus, load_license

logger = logging.getLogger(__name__)

EXPIRY_WARNING_DAYS = 30
HEARTBEAT_INTERVAL_SECONDS = 24 * 60 * 60


def _registry() -> FeatureRegistry:
    try:
        return FeatureRegistry.default(extra_files=extension_feature_files())
    except Exception:
        logger.exception("An extension package's feature registry could not be read; using Community's")
        return FeatureRegistry.default()


def _known(registry: FeatureRegistry, keys: frozenset[str]) -> tuple[frozenset[str], frozenset[str]]:
    known: set[str] = set()
    for key in keys:
        try:
            registry.get(key)
        except ValueError:
            continue
        known.add(key)
    return frozenset(known), keys - known


def resolve_edition(
    settings: Any,
    *,
    license_state: LicenseState | None = None,
    extensions: tuple[ExtensionMount, ...] = (),
) -> EditionState:
    """Apply the license to ``settings`` and return the edition it gives."""
    state = license_state or load_license(
        settings.enterprise_license_path, settings.enterprise_license_public_key_path
    )
    registry = _registry()
    ignored: frozenset[str] = frozenset()
    if state.status is LicenseStatus.ACTIVE:
        granted, ignored = _known(registry, state.entitlements)
        settings.platform_edition = "enterprise"
        settings.platform_entitlements = sorted(granted)
        if ignored:
            logger.warning(
                "The license grants feature keys no installed package defines: %s",
                ", ".join(sorted(ignored)),
            )
    elif state.status is not LicenseStatus.ABSENT:
        settings.platform_edition = "community"
        settings.platform_entitlements = []
        logger.error("Enterprise license not applied, running as Community: %s", state.reason)
    elif str(settings.platform_edition).strip().lower() != "community":
        logger.warning(
            "PLATFORM_EDITION is %s but no license is configured (ENTERPRISE_LICENSE_PATH)",
            settings.platform_edition,
        )
    try:
        enabled = resolve_enabled_features(
            edition=settings.platform_edition,
            entitlement_keys=settings.platform_entitlements,
            registry=registry,
        )
    except ValueError:
        logger.exception("The configured entitlements do not resolve; running with Community features")
        enabled = resolve_enabled_features(edition="community", registry=registry)
    edition = EditionState(
        edition=str(settings.platform_edition).strip().lower(),
        license=state,
        enabled_features=enabled,
        ignored_entitlements=ignored,
        extensions=extensions,
    )
    set_current_edition(edition)
    if state.status is LicenseStatus.ACTIVE and state.license is not None:
        logger.info(
            "Enterprise license %s for %s active until %s",
            state.license.license_id,
            state.license.customer_id,
            state.license.expires_at.isoformat(),
        )
    return edition


async def metering_month_to_date(session_factory: Callable[[], Any], today: date | None = None) -> dict[str, int]:
    """Deployment-wide metered calls, principals and keys since the 1st of the month."""
    from app.kernel.runtime.db.models.usage import UsageDailyAggregate

    day = today or datetime.now(UTC).date()
    since = day.replace(day=1)
    query = select(
        func.coalesce(func.sum(UsageDailyAggregate.call_count), 0),
        func.count(distinct(UsageDailyAggregate.user_id)).filter(UsageDailyAggregate.user_id != ""),
        func.count(distinct(UsageDailyAggregate.api_key_id)).filter(UsageDailyAggregate.api_key_id != ""),
    ).where(UsageDailyAggregate.day >= since)
    async with session_factory() as session:
        calls, principals, keys = (await session.execute(query)).one()
    return {"metered_calls": int(calls), "active_principals": int(principals), "active_api_keys": int(keys)}


async def license_heartbeat(settings: Any, session_factory: Callable[[], Any]) -> EditionState:
    """Re-check the license, apply a lapse, and log its state with the month's metering."""
    previous = current_edition()
    state = load_license(settings.enterprise_license_path, settings.enterprise_license_public_key_path)
    edition = previous
    if state.status is not previous.license.status or state.license != previous.license.license:
        edition = resolve_edition(settings, license_state=state, extensions=previous.extensions)
    try:
        metering = await metering_month_to_date(session_factory)
    except Exception:
        logger.warning("License heartbeat could not read the usage aggregates", exc_info=True)
        metering = {}
    info = state.license
    days_left = state.days_left()
    level = logging.INFO
    if state.status is not LicenseStatus.ACTIVE or (days_left is not None and days_left <= EXPIRY_WARNING_DAYS):
        level = logging.WARNING
    logger.log(
        level,
        "license.heartbeat status=%s edition=%s license_id=%s days_left=%s",
        state.status.value,
        edition.edition,
        info.license_id if info else None,
        days_left,
        extra={
            "event": "license.heartbeat",
            "license_status": state.status.value,
            "edition": edition.edition,
            "license_id": info.license_id if info else None,
            "customer_id": info.customer_id if info else None,
            "expires_at": info.expires_at.isoformat() if info else None,
            "days_left": days_left,
            "reason": state.reason,
            **metering,
        },
    )
    return edition


async def run_license_heartbeat(
    settings: Any,
    session_factory: Callable[[], Any],
    *,
    interval_seconds: float = HEARTBEAT_INTERVAL_SECONDS,
) -> None:
    while True:
        try:
            await license_heartbeat(settings, session_factory)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("License heartbeat failed")
        await asyncio.sleep(interval_seconds)
