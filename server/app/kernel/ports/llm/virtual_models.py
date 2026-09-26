""" virtual_models

A virtual model is a workspace name for an ordered list of model refs.

A call names it as ``vmodel:{slug}``. The LLM policy gateway resolves it to
its targets and tries them in order: a target whose route is unavailable
(provider or model disabled, removed, or lacking a capability the call needs)
is skipped, and a call that fails with an error worth retrying elsewhere
(a timeout, 408, 409, 429, a 5xx or a lost connection) moves on to the next
target once that target's own retries are spent. A request the provider
refused as invalid, or content refused by policy, does not move on: the next
target would refuse it too. Streams move on only before their first chunk.
"""

from __future__ import annotations

from typing import Protocol

from app.kernel.contracts.context import RequestContext

VIRTUAL_MODEL_PREFIX = "vmodel:"
"""Prefix of a virtual model ref; ``model:`` refs are concrete routes."""

MAX_VIRTUAL_MODEL_TARGETS = 8


def is_virtual_model(model: str) -> bool:
    return model.startswith(VIRTUAL_MODEL_PREFIX)


def virtual_model_slug(model: str) -> str:
    return model[len(VIRTUAL_MODEL_PREFIX) :]


def virtual_model_ref(slug: str) -> str:
    return f"{VIRTUAL_MODEL_PREFIX}{slug}"


class VirtualModelResolver(Protocol):
    """Looks up the targets of a workspace's virtual model."""

    async def resolve_targets(self, ctx: RequestContext, slug: str) -> list[str] | None:
        """The ordered model refs of an active virtual model, or None."""
        ...
