"""Per-call prices a tool declares in its ToolSpec policy.

A tool that bills (a search API, a scraper, a paid data source) declares
what one call costs::

    "policy": {"pricing": {"currency": "USD", "call": "0.002"}}

Each successful call then writes a priced cost row that counts against
budgets and credits like a model call; a failed call is recorded unpriced. A tool that declares no price stays
unpriced, and its row says so; ``"call": "0"`` is an explicit free price.
A price that cannot be read is never taken as zero: the row stays unpriced
and names the problem, and the call it prices has already run, so pricing
never fails it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

_CURRENCY = re.compile(r"^[A-Z]{3}$")
# The ToolSpec schema's own pattern: what the ledger's amount column holds,
# 12 integer and 6 fractional ASCII digits, written as a string.
_PRICE = re.compile(r"^(0|[1-9][0-9]{0,11})(\.[0-9]{1,6})?$", re.ASCII)


@dataclass(frozen=True)
class ToolCallPricing:
    """The price of one tool call and the snapshot that shows how it was set."""

    currency: str | None
    amount: Decimal | None
    snapshot: dict[str, Any]


def _price(value: Any) -> Decimal | None:
    # Held to the schema's pattern: an MCP server's policy is not validated
    # against the ToolSpec schema, so its prices are read no more loosely.
    if not isinstance(value, str) or not _PRICE.fullmatch(value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def unpriced_call(reason: str, *, tool_ref: str, configured: Any = None) -> ToolCallPricing:
    """An unpriced call, with the reason no price applies."""

    return _unpriced(reason, tool_ref=tool_ref, configured=configured)


def _unpriced(reason: str, *, tool_ref: str, configured: Any) -> ToolCallPricing:
    return ToolCallPricing(
        currency=None,
        amount=None,
        snapshot={
            "schema_version": 1,
            "source": "tool_spec",
            "priced": False,
            "reason": reason,
            "billing_basis": "requests",
            "tool_ref": tool_ref,
            "configured_pricing": configured,
        },
    )


def declared_call_pricing(policy: dict[str, Any] | None, *, tool_ref: str) -> ToolCallPricing:
    """Price one call of a tool from the ``pricing`` its policy declares."""

    configured = (policy or {}).get("pricing")
    if configured is None:
        return _unpriced("tool_pricing_not_declared", tool_ref=tool_ref, configured=None)
    if not isinstance(configured, dict):
        return _unpriced("unsupported_pricing_config", tool_ref=tool_ref, configured=None)
    currency = configured.get("currency")
    price = _price(configured.get("call"))
    unknown = set(configured) - {"currency", "call"}
    if not isinstance(currency, str) or not _CURRENCY.match(currency) or price is None or unknown:
        return _unpriced(
            "unsupported_pricing_config",
            tool_ref=tool_ref,
            configured={key: str(value) for key, value in configured.items()},
        )
    return ToolCallPricing(
        currency=currency,
        amount=price,
        snapshot={
            "schema_version": 1,
            "source": "tool_spec",
            "priced": True,
            "billing_basis": "requests",
            "billing_unit": "call",
            "unit_size": 1,
            "rates": {"call": {"price": format(price, "f"), "unit": "call", "unit_size": 1}},
            "quantities": {"requests": 1},
            "currency": currency,
            "amount": format(price, "f"),
            "tool_ref": tool_ref,
            "configured_pricing": {"currency": currency, "call": format(price, "f")},
        },
    )
