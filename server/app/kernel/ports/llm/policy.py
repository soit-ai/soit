""" policy

LLM port policies: timeout/retry/rate-limit/audit.
"""

import asyncio
import contextlib
import inspect
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, TypeVar

import anyio
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, Tracer

from app.kernel.commons.errors import (
    ForbiddenError,
    KernelError,
)
from app.kernel.commons.errors import TimeoutError as KernelTimeoutError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.api_key_admission import ApiKeyAdmission
from app.kernel.ports.common.credit import CreditGuard, check_spend
from app.kernel.ports.common.policy import (
    error_details,
    resolve_run_id,
)
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.common.spans import call_span, failure_label
from app.kernel.ports.common.usage_counter import (
    DailyUsageCounter,
)
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    ImageGenerationResponse,
    LLMPort,
    LLMRuntimeTarget,
    RerankResponse,
)
from app.kernel.ports.llm.runtime_config import validate_image_request
from app.kernel.ports.llm.usage_estimate import GeneratedText, estimate_prompt_tokens
from app.kernel.ports.llm.virtual_models import (
    VirtualModelResolver,
    is_virtual_model,
    virtual_model_slug,
)
from app.kernel.ports.safety.interface import (
    ContentSafetyPort,
    SafetyDecision,
    SafetyDirection,
)
from app.kernel.runtime.runs.content_capture import writer_capture
from app.kernel.runtime.runs.writer import TraceWriter

logger = logging.getLogger(__name__)

STREAM_ABANDONED = "STREAM_ABANDONED"
# Bounds on closing a model call once its stream ends, which runs shielded
# from the consumer's cancellation: closing the provider stream, then writing
# the ledger (longer than a pooled connection may take to check out).
_PROVIDER_CLOSE_TIMEOUT_SECONDS = 5.0
_SETTLE_TIMEOUT_SECONDS = 60.0
# Marks a cost row whose tokens were estimated because the provider never
# reported them (see usage_estimate): about right for text, a lower bound
# for images and for reasoning the provider does not stream.
_USAGE_ESTIMATE_SNAPSHOT = {"usage_estimated": True, "usage_estimate_basis": "characters"}
# Marks an image charge whose count was never confirmed: the provider was asked
# for the images and its answer never came, so the count is what was asked for.
_IMAGE_ESTIMATE_SNAPSHOT = {"usage_estimated": True, "usage_estimate_basis": "requested_images"}


def _closing_a_dropped_generator() -> bool:
    """Whether the running task exists only to close an unclosed async generator.

    asyncio closes an async generator that was collected while still open,
    and every open one at loop shutdown, from a task of its own whose
    coroutine is the generator's ``aclose()``. That task shares nothing with
    the code that consumed the stream and must not write through its session.
    Any other close is the consumer's own, whichever task makes it.
    """
    task = asyncio.current_task()
    return task is not None and type(task.get_coro()).__name__ == "async_generator_athrow"


def _provider_from_model(model_ref: str | None) -> str | None:
    if not model_ref:
        return None
    if model_ref.startswith("model:"):
        parts = model_ref.split(":")
        if len(parts) >= 2:
            return parts[1]
    return None


def _runtime_cost_fields(
    *,
    requested_model: str,
    upstream_model: str | None,
    target: LLMRuntimeTarget | None,
) -> dict[str, str | None]:
    if target is not None:
        return {
            "provider": target.provider_kind,
            "provider_id": target.provider_id,
            "provider_slug": target.provider_slug,
            "provider_kind": target.provider_kind,
            "model_ref": target.model_ref,
            "upstream_model": upstream_model,
        }
    model_used = upstream_model or requested_model
    provider = _provider_from_model(model_used)
    return {
        "provider": provider,
        "provider_id": None,
        "provider_slug": provider,
        "provider_kind": provider,
        "model_ref": model_used,
        "upstream_model": upstream_model,
    }


def _capped_retries(max_retries: int, cap: int | None) -> int:
    """Clamp a route retry budget to an operation-specific ceiling."""
    return max_retries if cap is None else min(max_retries, cap)


_CallResult = TypeVar("_CallResult")

# Route failures that mean "this target cannot serve the call right now";
# a virtual model moves on to its next target instead of failing.
_UNAVAILABLE_ROUTE_CODES = frozenset(
    {
        "MODEL_PROVIDER_DISABLED",
        "MODEL_RUNTIME_DISABLED",
        "MODEL_RUNTIME_NOT_FOUND",
        "MODEL_CAPABILITY_UNAVAILABLE",
    }
)


@dataclass(frozen=True)
class _ResolvedPolicyRoute:
    port: LLMPort
    target: LLMRuntimeTarget | None
    timeout_seconds: float
    max_retries: int
    retry_backoff: str
    retryable_status_codes: tuple[int, ...]
    pricing: dict[str, Any]
    image_capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _PricingCalculation:
    """Calculated amount and immutable pricing evidence for one usage fact."""

    currency: str | None
    amount: Decimal | None
    snapshot: dict[str, Any]


_TOKEN_UNIT_SIZES = {
    "token": 1,
    "tokens": 1,
    "ktok": 1_000,
    "1k_tokens": 1_000,
    "thousand_tokens": 1_000,
    "mtok": 1_000_000,
    "1m_tokens": 1_000_000,
    "million_tokens": 1_000_000,
}
_SEARCH_UNIT_SIZES = {
    "search": 1,
    "searches": 1,
    "1k_searches": 1_000,
    "kilo_searches": 1_000,
}
_IMAGE_UNIT_SIZES = {
    "image": 1,
    "images": 1,
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _pricing_source(pricing: dict[str, Any]) -> str:
    source = pricing.get("pricing_source")
    return str(source).strip() if source else "provider_model"


def _unpriced_calculation(
    pricing: dict[str, Any],
    *,
    billing_basis: str,
    quantities: dict[str, Any],
    reason: str | None = None,
) -> _PricingCalculation:
    resolved_reason = reason or (
        "pricing_not_configured" if not pricing else "unsupported_pricing_config"
    )
    return _PricingCalculation(
        currency=None,
        amount=None,
        snapshot={
            "schema_version": 1,
            "source": _pricing_source(pricing),
            "priced": False,
            "reason": resolved_reason,
            "billing_basis": billing_basis,
            "billing_unit": None,
            "unit_size": None,
            "rates": {},
            "quantities": quantities,
            "currency": None,
            "amount": None,
            "configured_pricing": _json_safe(pricing),
        },
    )


def _rate_definition(
    pricing: dict[str, Any],
    *,
    nested_key: str,
    flat_key: str,
    unit_key: str,
    unit_sizes: dict[str, int],
    default_unit: str | None = None,
) -> tuple[Decimal, str, int] | None:
    raw_rate = pricing.get(nested_key)
    if raw_rate is None and nested_key != flat_key:
        raw_rate = pricing.get(flat_key)
    if isinstance(raw_rate, dict):
        raw_amount = raw_rate.get("amount", raw_rate.get("price"))
        raw_unit = raw_rate.get(
            "unit",
            pricing.get(unit_key, pricing.get("unit", default_unit)),
        )
    else:
        raw_amount = raw_rate
        raw_unit = pricing.get(unit_key, pricing.get("unit", default_unit))
    if raw_amount is None or raw_unit is None:
        return None
    try:
        rate = Decimal(str(raw_amount))
    except (InvalidOperation, TypeError, ValueError):
        return None
    unit = str(raw_unit).strip().lower()
    unit_size = unit_sizes.get(unit)
    if rate < 0 or unit_size is None:
        return None
    return rate, unit, unit_size


def _priced_calculation(
    pricing: dict[str, Any],
    *,
    billing_basis: str,
    rates: dict[str, tuple[Decimal, str, int]],
    quantities: dict[str, Any],
    amount: Decimal,
    currency: str,
) -> _PricingCalculation:
    normalized_rates = {
        key: {
            "price": format(rate, "f"),
            "unit": unit,
            "unit_size": unit_size,
        }
        for key, (rate, unit, unit_size) in rates.items()
    }
    unit_pairs = {(unit, unit_size) for _, unit, unit_size in rates.values()}
    if len(unit_pairs) == 1:
        billing_unit, unit_size = next(iter(unit_pairs))
    else:
        billing_unit, unit_size = "mixed", None
    return _PricingCalculation(
        currency=currency,
        amount=amount,
        snapshot={
            "schema_version": 1,
            "source": _pricing_source(pricing),
            "priced": True,
            "billing_basis": billing_basis,
            "billing_unit": billing_unit,
            "unit_size": unit_size,
            "rates": normalized_rates,
            "quantities": quantities,
            "currency": currency,
            "amount": format(amount, "f"),
            "configured_pricing": _json_safe(pricing),
        },
    )


def _token_pricing(
    pricing: dict[str, Any],
    *,
    prompt_tokens: int,
    completion_tokens: int = 0,
    require_output_rate: bool = True,
) -> _PricingCalculation:
    """Calculate token pricing and preserve both configured and normalized rates."""
    quantities = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    try:
        currency = str(pricing["currency"]).strip().upper()
    except (KeyError, TypeError, ValueError):
        return _unpriced_calculation(
            pricing,
            billing_basis="tokens",
            quantities=quantities,
        )
    input_rate = _rate_definition(
        pricing,
        nested_key="prompt",
        flat_key="input",
        unit_key="input_unit",
        unit_sizes=_TOKEN_UNIT_SIZES,
    )
    output_rate = _rate_definition(
        pricing,
        nested_key="completion",
        flat_key="output",
        unit_key="output_unit",
        unit_sizes=_TOKEN_UNIT_SIZES,
    )
    if not currency or input_rate is None or (
        require_output_rate and output_rate is None
    ):
        return _unpriced_calculation(
            pricing,
            billing_basis="tokens",
            quantities=quantities,
        )
    rates = {"input": input_rate}
    amount = Decimal(prompt_tokens) * input_rate[0] / Decimal(input_rate[2])
    if output_rate is not None:
        rates["output"] = output_rate
        amount += (
            Decimal(completion_tokens)
            * output_rate[0]
            / Decimal(output_rate[2])
        )
    return _priced_calculation(
        pricing,
        billing_basis="tokens",
        rates=rates,
        quantities=quantities,
        amount=amount,
        currency=currency,
    )


def _chat_pricing(
    pricing: dict[str, Any],
    *,
    prompt_tokens: int,
    completion_tokens: int,
) -> _PricingCalculation:
    """Chat pricing requires both input and output token rates."""
    return _token_pricing(
        pricing,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


def _embed_pricing(
    pricing: dict[str, Any],
    *,
    tokens_used: int,
) -> _PricingCalculation:
    """Embeddings bill input tokens only; the output rate is optional."""
    return _token_pricing(
        pricing,
        prompt_tokens=max(tokens_used, 0),
        require_output_rate=False,
    )


def _rerank_pricing(
    pricing: dict[str, Any],
    *,
    searches: int,
    tokens_used: int,
) -> _PricingCalculation:
    """Per-search pricing takes precedence; token pricing is the fallback."""
    quantities = {"searches": searches, "total_tokens": tokens_used}
    if "search" in pricing:
        try:
            currency = str(pricing["currency"]).strip().upper()
        except (KeyError, TypeError, ValueError):
            return _unpriced_calculation(
                pricing,
                billing_basis="searches",
                quantities=quantities,
            )
        search_rate = _rate_definition(
            pricing,
            nested_key="search",
            flat_key="search",
            unit_key="search_unit",
            unit_sizes=_SEARCH_UNIT_SIZES,
            default_unit="1k_searches",
        )
        if not currency or search_rate is None:
            return _unpriced_calculation(
                pricing,
                billing_basis="searches",
                quantities=quantities,
            )
        amount = Decimal(searches) * search_rate[0] / Decimal(search_rate[2])
        return _priced_calculation(
            pricing,
            billing_basis="searches",
            rates={"search": search_rate},
            quantities=quantities,
            amount=amount,
            currency=currency,
        )
    calculation = _token_pricing(
        pricing,
        prompt_tokens=max(tokens_used, 0),
        require_output_rate=False,
    )
    calculation.snapshot["quantities"]["searches"] = searches
    return calculation


def _image_pricing(
    pricing: dict[str, Any],
    *,
    image_count: int,
    size: str | None = None,
    quality: str | None = None,
    steps: int | None = None,
    unpriced_reason: str | None = None,
) -> _PricingCalculation:
    """Images bill per generated image; pricing key "image" with unit "image".

    Diffusion cost tracks resolution and step count, not image count, so the
    request shape is recorded alongside the quantity even while the rate stays
    per-image. Without it the images column reconciles against a number that
    cannot explain itself: four 4096px images and four 256px images bill
    identically and leave no evidence of the difference.
    """
    quantities: dict[str, Any] = {"images": image_count}
    if size:
        quantities["size"] = size
    if quality:
        quantities["quality"] = quality
    if steps is not None:
        quantities["steps"] = steps
    try:
        currency = str(pricing["currency"]).strip().upper()
    except (KeyError, TypeError, ValueError):
        return _unpriced_calculation(
            pricing,
            billing_basis="images",
            quantities=quantities,
            reason=unpriced_reason,
        )
    image_rate = _rate_definition(
        pricing,
        nested_key="image",
        flat_key="image",
        unit_key="image_unit",
        unit_sizes=_IMAGE_UNIT_SIZES,
        default_unit="image",
    )
    if not currency or image_rate is None:
        return _unpriced_calculation(
            pricing,
            billing_basis="images",
            quantities=quantities,
            reason=unpriced_reason,
        )
    amount = Decimal(image_count) * image_rate[0] / Decimal(image_rate[2])
    return _priced_calculation(
        pricing,
        billing_basis="images",
        rates={"image": image_rate},
        quantities=quantities,
        amount=amount,
        currency=currency,
    )


def unconfirmed_image_charge(
    pricing: dict[str, Any],
    *,
    requested_model: str,
    target: LLMRuntimeTarget | None,
    images: int,
    size: str | None = None,
    unpriced_reason: str | None = None,
) -> tuple[_PricingCalculation, dict[str, str | None]]:
    """The charge for an image call whose answer never came, and its cost identity.

    The provider was asked for ``images`` images and nothing came back, a
    timeout or a process that stopped mid-call. It does not cancel the work
    and may still make and bill every image, so the call is charged the
    count it asked for, flagged as estimated. ``unpriced_reason`` says why a
    charge has no price when the reason is not the pricing itself, such as
    a route that no longer resolves.
    """
    identity = _runtime_cost_fields(requested_model=requested_model, upstream_model=None, target=target)
    calculation = _with_runtime_identity(
        _image_pricing(pricing, image_count=images, size=size, unpriced_reason=unpriced_reason),
        requested_model=requested_model,
        identity=identity,
    )
    return (
        _PricingCalculation(
            currency=calculation.currency,
            amount=calculation.amount,
            snapshot={**calculation.snapshot, **_IMAGE_ESTIMATE_SNAPSHOT},
        ),
        identity,
    )


def _with_runtime_identity(
    calculation: _PricingCalculation,
    *,
    requested_model: str,
    identity: dict[str, str | None],
) -> _PricingCalculation:
    snapshot = dict(calculation.snapshot)
    snapshot["model"] = {
        "requested": requested_model,
        "resolved": identity["model_ref"],
        "upstream": identity["upstream_model"],
    }
    snapshot["provider"] = {
        "name": identity["provider"],
        "id": identity["provider_id"],
        "slug": identity["provider_slug"],
        "kind": identity["provider_kind"],
    }
    return _PricingCalculation(
        currency=calculation.currency,
        amount=calculation.amount,
        snapshot=snapshot,
    )


# Where streamed text may be cut for inspection: after a line break, after
# sentence punctuation that is followed by whitespace (a bare "." sits inside
# URLs, versions and JWTs), or after CJK sentence punctuation.
_STREAM_SENTENCE_END = re.compile(r"\n|[.!?](?=\s)|[\u3002\uff01\uff1f]")
# Upper bound on how much streamed text is held back before inspection. Past
# it the text is cut at the last whitespace, so a credential is not split.
_STREAM_MAX_HOLD = 400


def _stream_cut_point(pending: str) -> int | None:
    last_end = None
    for match in _STREAM_SENTENCE_END.finditer(pending):
        last_end = match.end()
    if last_end is not None:
        return last_end
    if len(pending) < _STREAM_MAX_HOLD:
        return None
    whitespace = max(pending.rfind(" "), pending.rfind("\t"))
    return whitespace + 1 if whitespace > 0 else len(pending)


def _chunk_carries_signal(chunk: ChatStreamChunk) -> bool:
    """Whether a chunk means something to the consumer besides its text."""

    return bool(
        chunk.done
        or chunk.finish_reason
        or chunk.tool_call_deltas
        or chunk.tool_calls
        or chunk.reasoning_delta
        or chunk.tokens_prompt
        or chunk.tokens_completion
        or chunk.hosted_tool_calls
        or chunk.citations
        or chunk.hosted_artifacts
    )


class _OutboundStreamInspector:
    """Inspect streamed model output a sentence at a time.

    Content safety judges whole spans of text, and a redaction has to replace
    text before the client sees it, so streamed deltas are held back until a
    sentence ends (or the held text grows past ``_STREAM_MAX_HOLD``), then the
    span is inspected and released, redacted if the policy says so. A refusal
    raises and ends the stream. What reaches the client is exactly what was
    inspected.
    """

    def __init__(self, gateway: "LLMPolicyGateway", evidence: list[dict[str, Any]]) -> None:
        self._gateway = gateway
        self._evidence = evidence
        self._pending = ""

    async def feed(self, delta: str) -> str:
        self._pending += delta
        cut = _stream_cut_point(self._pending)
        if cut is None:
            return ""
        segment, self._pending = self._pending[:cut], self._pending[cut:]
        return await self._release(segment)

    async def flush(self) -> str:
        segment, self._pending = self._pending, ""
        return await self._release(segment)

    async def _release(self, segment: str) -> str:
        if not segment:
            return ""
        released = await self._gateway._inspect(
            segment,
            direction=SafetyDirection.OUTBOUND,
            evidence=self._evidence,
        )
        return released or ""


class LLMPolicyGateway(LLMPort):
    """LLM port with policy enforcement."""

    def __init__(
        self,
        gateway: LLMPort,
        ctx: RequestContext,
        trace_writer: TraceWriter | None = None,
        timeout_seconds: float = 60,
        max_retries: int = 3,
        rate_limit_per_minute: int | None = None,
        daily_quota: int | None = None,
        rate_limiter: RateLimiter | None = None,
        otel_tracer: Tracer | None = None,
        retry_backoff_base_seconds: float = 0.5,
        retry_backoff: str = "exponential",
        retryable_status_codes: tuple[int, ...] = (408, 409, 429, 500, 502, 503, 504),
        credit_guard: CreditGuard | None = None,
        image_timeout_seconds: float = 300.0,
        image_max_retries: int = 0,
        content_safety: ContentSafetyPort | None = None,
        inspect_inbound: bool = True,
        inspect_outbound: bool = True,
        usage_counter: DailyUsageCounter | None = None,
        virtual_models: VirtualModelResolver | None = None,
    ):
        """Initialize policy gateway.

        Args:
            gateway: Underlying LLM port.
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            timeout_seconds: Fallback request timeout in seconds, used when the
                resolved route carries no timeout of its own (every static
                platform-key provider). Production wiring passes
                ``settings.llm_timeout_seconds``; this default only applies to
                direct construction such as tests.
            max_retries: Maximum retry attempts.
            rate_limit_per_minute: Optional rate limit per minute.
            daily_quota: Optional daily request quota.
            rate_limiter: Optional rate limiter instance.
            image_timeout_seconds: Fallback request timeout for image
                generation, which is slower than chat.
            image_max_retries: Retry ceiling for image generation. A retried
                image call can bill the provider twice for one recorded usage
                fact, so the default suppresses route-configured retries.
        """
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.rate_limit_per_minute = rate_limit_per_minute
        self.daily_quota = daily_quota
        self.rate_limiter = rate_limiter or RateLimiter()
        self.otel_tracer = otel_tracer or trace.get_tracer("soit.llm")
        self.retry_backoff_base_seconds = max(0.0, retry_backoff_base_seconds)
        self.retry_backoff = retry_backoff
        self.retryable_status_codes = retryable_status_codes
        self.credit_guard = credit_guard
        self.image_timeout_seconds = image_timeout_seconds
        self.image_max_retries = image_max_retries
        # None means the deployment has no content inspection. That is "no such
        # capability", never "everything is safe".
        self.content_safety = content_safety
        self.inspect_inbound = inspect_inbound
        self.inspect_outbound = inspect_outbound
        self.usage_counter = usage_counter or DailyUsageCounter()
        self.virtual_models = virtual_models

    async def _inspect(
        self,
        text: str | None,
        *,
        direction: SafetyDirection,
        evidence: list[dict[str, Any]],
    ) -> str | None:
        """Return the text to use, recording what the check found.

        A refusal raises; a redaction returns the replacement; anything else
        returns the text unchanged. Every outcome with findings is appended to
        `evidence`, which is written onto the run step, so a decision that
        changed the content is visible afterwards rather than only in the
        moment.
        """
        if self.content_safety is None or not text:
            return text

        verdict = await self.content_safety.inspect(text, direction=direction)
        if verdict.findings:
            evidence.append({**verdict.evidence(), "direction": direction.value})
        if verdict.decision is SafetyDecision.BLOCK:
            raise ForbiddenError(
                "Content refused by the content safety policy",
                {
                    "direction": direction.value,
                    "provider": verdict.provider,
                    "categories": [finding.category for finding in verdict.findings],
                },
            )
        if verdict.decision is SafetyDecision.REDACT and verdict.redacted_text is not None:
            return verdict.redacted_text
        return text

    async def _inspect_messages(
        self,
        messages: list[ChatMessage],
        evidence: list[dict[str, Any]],
    ) -> list[ChatMessage]:
        """Inspect what is about to be sent to a model.

        The prompt is where user input and retrieved documents have already
        been assembled, so it is the one place that sees all of it.
        """
        if self.content_safety is None or not self.inspect_inbound:
            return messages

        inspected: list[ChatMessage] = []
        changed = False
        for message in messages:
            content = await self._inspect(
                message.content,
                direction=SafetyDirection.INBOUND,
                evidence=evidence,
            )
            if content == message.content:
                inspected.append(message)
                continue
            changed = True
            inspected.append(
                ChatMessage(
                    role=message.role,
                    content=content,
                    tool_call_id=getattr(message, "tool_call_id", None),
                    tool_calls=getattr(message, "tool_calls", None),
                    name=getattr(message, "name", None),
                    images=getattr(message, "images", None),
                )
            )
        return inspected if changed else messages

    async def _resolve_call_route(
        self,
        model: str,
        required_capabilities: tuple[str, ...],
        *,
        timeout_fallback: float | None = None,
        max_retries_cap: int | None = None,
    ) -> _ResolvedPolicyRoute:
        fallback_timeout = timeout_fallback or self.timeout_seconds
        resolver = getattr(type(self.gateway), "resolve_route", None)
        if resolver is None:
            return _ResolvedPolicyRoute(
                port=self.gateway,
                target=None,
                timeout_seconds=fallback_timeout,
                max_retries=_capped_retries(self.max_retries, max_retries_cap),
                retry_backoff=self.retry_backoff,
                retryable_status_codes=self.retryable_status_codes,
                pricing={},
            )
        route = resolver(self.gateway, model, self.ctx, required_capabilities)
        if inspect.isawaitable(route):
            route = await route
        return _ResolvedPolicyRoute(
            port=route.port,
            target=route.target,
            timeout_seconds=route.timeout_seconds or fallback_timeout,
            max_retries=_capped_retries(
                self.max_retries if route.max_retries is None else route.max_retries,
                max_retries_cap,
            ),
            retry_backoff=route.retry_backoff,
            retryable_status_codes=route.retryable_status_codes,
            pricing=route.pricing,
            image_capabilities=getattr(route, "image_capabilities", None) or {},
        )

    @staticmethod
    def _is_retryable(exc: Exception, retryable_status_codes: tuple[int, ...]) -> bool:
        if isinstance(exc, KernelError):
            return False
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            return int(status_code) in retryable_status_codes
        return exc.__class__.__name__ not in {
            "AuthenticationError",
            "PermissionDeniedError",
            "BadRequestError",
            "UnprocessableEntityError",
        }

    async def _run_call(
        self,
        operation,
        *,
        timeout_factory,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_backoff: str = "exponential",
        retryable_status_codes: tuple[int, ...] | None = None,
    ):
        call_timeout = timeout_seconds or self.timeout_seconds
        retries = self.max_retries if max_retries is None else max_retries
        status_codes = retryable_status_codes or self.retryable_status_codes
        for attempt in range(retries + 1):
            try:
                return await asyncio.wait_for(operation(), timeout=call_timeout)
            except TimeoutError:
                if attempt >= retries:
                    raise timeout_factory() from None
            except Exception as exc:
                if attempt >= retries or not self._is_retryable(exc, status_codes):
                    raise
            if retry_backoff != "none" and self.retry_backoff_base_seconds:
                multiplier = 2**attempt if retry_backoff == "exponential" else 1
                delay = min(self.retry_backoff_base_seconds * multiplier, 5.0)
                await asyncio.sleep(delay)
        raise RuntimeError("LLM retry loop exhausted")

    async def _targets(self, model: str) -> list[str]:
        """The concrete model refs a call to ``model`` may be served by, in order."""
        if not is_virtual_model(model):
            return [model]
        targets = (
            await self.virtual_models.resolve_targets(self.ctx, virtual_model_slug(model))
            if self.virtual_models is not None
            else None
        )
        if not targets:
            raise KernelError(
                "MODEL_RUNTIME_NOT_FOUND",
                f"Virtual model was not found: {model}",
                {"model": model},
            )
        return targets

    def _fails_over(self, exc: Exception, route: _ResolvedPolicyRoute) -> bool:
        """Whether another target may succeed where this one failed.

        Timeouts, rate limits, server errors and lost connections are the
        provider's trouble; an invalid request or a policy refusal would be
        refused by the next target too.
        """
        if isinstance(exc, KernelTimeoutError):
            return True
        return self._is_retryable(exc, route.retryable_status_codes)

    async def _call_with_failover(
        self,
        model: str,
        required_capabilities: tuple[str, ...],
        invoke: Callable[[_ResolvedPolicyRoute, str], Awaitable[_CallResult]],
        *,
        operation: str,
    ) -> tuple[_ResolvedPolicyRoute, _CallResult, list[dict[str, Any]]]:
        """Call the first target that serves the request.

        For a concrete model this is the one route with its own retries. For
        a virtual model the attempts are returned as run evidence.
        """
        targets = await self._targets(model)
        attempts: list[dict[str, Any]] = []
        for index, target in enumerate(targets):
            last = index == len(targets) - 1
            try:
                route = await self._resolve_call_route(target, required_capabilities)
            except KernelError as exc:
                if last or exc.code not in _UNAVAILABLE_ROUTE_CODES:
                    raise
                attempts.append({"model_ref": target, "outcome": "unavailable", "reason": exc.code})
                continue
            try:
                result = await self._run_call(
                    lambda route=route, target=target: invoke(route, target),
                    timeout_factory=lambda route=route, target=target: KernelTimeoutError(
                        f"{operation} timed out after {route.timeout_seconds} seconds",
                        {"timeout_seconds": route.timeout_seconds, "model": target},
                    ),
                    timeout_seconds=route.timeout_seconds,
                    max_retries=route.max_retries,
                    retry_backoff=route.retry_backoff,
                    retryable_status_codes=route.retryable_status_codes,
                )
            except Exception as exc:
                if last or not self._fails_over(exc, route):
                    raise
                attempts.append({"model_ref": target, "outcome": "failed", "reason": failure_label(exc)})
                continue
            if len(targets) > 1:
                attempts.append({"model_ref": target, "outcome": "succeeded"})
            return route, result, attempts
        raise KernelError("MODEL_RUNTIME_NOT_FOUND", f"No model could serve: {model}")

    async def _first_available_route(
        self,
        model: str,
        required_capabilities: tuple[str, ...],
        *,
        timeout_fallback: float | None = None,
        max_retries_cap: int | None = None,
    ) -> tuple[_ResolvedPolicyRoute, str, list[dict[str, Any]]]:
        """The first target whose route resolves, without failing over on calls.

        Image calls use this: a failed image call may still have been billed,
        so it is not repeated on another provider.
        """
        targets = await self._targets(model)
        attempts: list[dict[str, Any]] = []
        for index, target in enumerate(targets):
            try:
                route = await self._resolve_call_route(
                    target,
                    required_capabilities,
                    timeout_fallback=timeout_fallback,
                    max_retries_cap=max_retries_cap,
                )
            except KernelError as exc:
                if index == len(targets) - 1 or exc.code not in _UNAVAILABLE_ROUTE_CODES:
                    raise
                attempts.append({"model_ref": target, "outcome": "unavailable", "reason": exc.code})
                continue
            if len(targets) > 1:
                attempts.append({"model_ref": target, "outcome": "selected"})
            return route, target, attempts
        raise KernelError("MODEL_RUNTIME_NOT_FOUND", f"No model could serve: {model}")

    async def _open_stream(
        self,
        route: _ResolvedPolicyRoute,
        target: str,
        request: dict[str, Any],
    ) -> tuple[Any, ChatStreamChunk | None]:
        """Open a stream on one route and wait for its first chunk, with retries."""
        aiter = None
        for attempt in range(route.max_retries + 1):
            try:
                stream = route.port.stream_chat(model=target, ctx=self.ctx, **request)
                if inspect.isawaitable(stream):
                    stream = await asyncio.wait_for(stream, timeout=route.timeout_seconds)
                aiter = stream.__aiter__()
                first_chunk = await asyncio.wait_for(
                    aiter.__anext__(),
                    timeout=route.timeout_seconds,
                )
                first_chunk.runtime_target = first_chunk.runtime_target or route.target
                return aiter, first_chunk
            except StopAsyncIteration:
                return aiter, None
            except TimeoutError:
                if attempt >= route.max_retries:
                    raise KernelTimeoutError(
                        f"LLM stream request timed out after {route.timeout_seconds} seconds",
                        {"timeout_seconds": route.timeout_seconds, "model": target},
                    ) from None
            except Exception as exc:
                if attempt >= route.max_retries or not self._is_retryable(
                    exc,
                    route.retryable_status_codes,
                ):
                    raise
            if route.retry_backoff != "none" and self.retry_backoff_base_seconds:
                multiplier = 2**attempt if route.retry_backoff == "exponential" else 1
                await asyncio.sleep(min(self.retry_backoff_base_seconds * multiplier, 5.0))
        return aiter, None

    async def _check_daily_quota(self, *, key_suffix: str) -> None:
        if not self.daily_quota:
            return
        quota_key = f"quota:llm:{key_suffix}:{self.ctx.tenant_id}:{self.ctx.workspace_id}"
        await self.rate_limiter.check_rate_limit(
            key=quota_key,
            limit=self.daily_quota,
            window_seconds=86400,
        )

    async def _admit(
        self,
        *,
        model: str,
        family: str,
        credit_operation: str,
        run_id: str | None = None,
    ) -> None:
        """Every check a call passes before it reaches a provider.

        A model the credential may not use is refused first, before the call
        spends any rate or quota budget; the member's limits come before the
        key's, and the credit check, which reads the ledger, comes last.
        """
        self._check_model_allowed(model)
        if self.rate_limit_per_minute:
            await self.rate_limiter.check_rate_limit(
                key=f"llm:{family}:{self.ctx.tenant_id}:{self.ctx.workspace_id}:{self.ctx.user_id}",
                limit=self.rate_limit_per_minute,
                window_seconds=60,
            )
        await self._check_daily_quota(key_suffix=family)
        await self._check_api_key_limits()
        if self.credit_guard:
            await check_spend(self.credit_guard, operation=credit_operation, run_id=run_id)

    def _check_model_allowed(self, model: str) -> None:
        allowed = self.ctx.allowed_models
        if allowed is not None and model not in allowed:
            raise ForbiddenError(
                "This API key may not call this model",
                {"param": "model", "model": model, "reason": "model_not_allowed"},
            )

    async def _keeps_content(self) -> bool:
        """Whether spans may carry exception text, which may echo input."""
        return (await writer_capture(self.trace_writer, self.ctx)).keeps_content

    def _key_admission(self) -> ApiKeyAdmission:
        return ApiKeyAdmission(
            self.ctx, rate_limiter=self.rate_limiter, usage_counter=self.usage_counter
        )

    async def _check_api_key_limits(self) -> None:
        # The same counters a direct tool call spends: one key, one budget.
        # A model call made for a tool call that already spent them does not
        # spend them twice.
        admission = self._key_admission()
        if not self.ctx.api_key_requests_spent:
            await admission.admit_request()
        await admission.check_tokens()

    async def _count_api_key_tokens(self, tokens: int) -> None:
        """Add what a finished call used to its key's daily token total."""
        await self._key_admission().count_tokens(tokens)

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ChatResponse:
        """Chat completion with policy enforcement.

        Args:
            messages: List of chat messages.
            model: Model reference.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            **kwargs: Additional parameters.

        Returns:
            ChatResponse instance.
        """
        await self._admit(model=model, family="chat", credit_operation="chat", run_id=resolve_run_id(kwargs, self.ctx))

        # Audit log
        step = None
        step_id: str | None = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = await self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="llm",
                input_summary=f"model={model}, messages={len(messages)}",
                status="running",
            )
            step_id = step.id
            await self.trace_writer.release_before_wait()

        start_time = utc_now()
        safety_evidence: list[dict[str, Any]] = []
        # Set once the provider has answered: from then on the call is billed,
        # whatever SOIT then does with the answer.
        answered: tuple[_ResolvedPolicyRoute, ChatResponse, list[dict[str, Any]]] | None = None
        recorded = False

        async def record(
            status: str,
            *,
            error_code: str | None = None,
            error_message: str | None = None,
            error_details: dict[str, Any] | None = None,
        ) -> None:
            nonlocal recorded
            assert answered is not None
            recorded = True
            route, response, attempts = answered
            if step_id and self.trace_writer:
                await self._write_chat_ledger(
                    step_id,
                    status,
                    model=model,
                    route=route,
                    response=response,
                    attempts=attempts,
                    safety_evidence=safety_evidence,
                    elapsed_ms=int((utc_now() - start_time).total_seconds() * 1000),
                    run_id=resolve_run_id(kwargs, self.ctx),
                    error_code=error_code,
                    error_message=error_message,
                    error_details=error_details,
                )
            # After the ledger: the key's daily total must not keep the ledger
            # row from being written.
            try:
                await self._count_api_key_tokens(response.tokens_prompt + response.tokens_completion)
            except Exception:
                logger.warning("Could not add a chat call's tokens to its API key", exc_info=True)

        try:
            messages = await self._inspect_messages(messages, safety_evidence)
            required_capabilities = ("chat", "tools") if kwargs.get("tools") else ("chat",)
            with call_span(
                self.otel_tracer,
                "soit.llm.chat",
                keeps_content=await self._keeps_content(),
                attributes={
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": model,
                    "gen_ai.provider.name": _provider_from_model(model) or "unknown",
                    "soit.tenant.id": self.ctx.tenant_id,
                    "soit.workspace.id": self.ctx.workspace_id,
                    "soit.run.id": resolve_run_id(kwargs, self.ctx) or "",
                    "soit.step.id": step.id if step else "",
                },
            ) as span:
                route, response, attempts = await self._call_with_failover(
                    model,
                    required_capabilities,
                    lambda route, target: route.port.chat(
                        messages=messages,
                        model=target,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        ctx=self.ctx,
                        **kwargs,
                    ),
                    operation="LLM chat request",
                )
                response.runtime_target = response.runtime_target or route.target
                answered = (route, response, attempts)
                if self.inspect_outbound:
                    response.text = await self._inspect(
                        response.text,
                        direction=SafetyDirection.OUTBOUND,
                        evidence=safety_evidence,
                    )
                span.set_attribute("gen_ai.response.model", response.model or model)
                span.set_attribute("gen_ai.usage.input_tokens", response.tokens_prompt)
                span.set_attribute("gen_ai.usage.output_tokens", response.tokens_completion)

            await record("succeeded")
            return response
        except Exception as e:
            if answered is not None and not recorded:
                # The provider answered, and billed for it, before SOIT
                # refused the answer (an outbound block).
                try:
                    await record(
                        "failed",
                        error_code="LLM_ERROR",
                        error_message=str(e),
                        error_details=error_details(e),
                    )
                except Exception:
                    logger.warning("Could not record a refused chat answer", exc_info=True)
                    if step_id and self.trace_writer:
                        with contextlib.suppress(Exception):
                            await self.trace_writer.update_step_status(
                                step_id, "failed", error_code="LLM_ERROR", error_message=str(e)
                            )
            elif step_id and self.trace_writer:
                await self.trace_writer.update_step_status(
                    step_id,
                    "failed",
                    error_code="LLM_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise

    async def _write_chat_ledger(
        self,
        step_id: str,
        status: str,
        *,
        model: str,
        route: _ResolvedPolicyRoute,
        response: ChatResponse,
        attempts: list[dict[str, Any]],
        safety_evidence: list[dict[str, Any]],
        elapsed_ms: int,
        run_id: str | None,
        error_code: str | None,
        error_message: str | None,
        error_details: dict[str, Any] | None,
    ) -> None:
        """Close a whole chat call's step and write its one usage row."""
        assert self.trace_writer is not None
        model_used = response.model or model
        identity = _runtime_cost_fields(
            requested_model=model,
            upstream_model=response.model,
            target=response.runtime_target,
        )
        await self.trace_writer.update_step_status(
            step_id,
            status,
            # A refused answer is not kept, not even in the summary.
            output_summary=response.text[:100] if response.text and status == "succeeded" else None,
            metrics={
                "tokens_prompt": response.tokens_prompt,
                "tokens_completion": response.tokens_completion,
                "latency_ms": elapsed_ms,
                **({"attempts": attempts} if attempts else {}),
                "model": model_used,
                "model_ref": identity["model_ref"],
                "provider_id": identity["provider_id"],
                "provider_slug": identity["provider_slug"],
                "provider_kind": identity["provider_kind"],
                "upstream_model": identity["upstream_model"],
                **({"content_safety": safety_evidence} if safety_evidence else {}),
            },
            error_code=error_code,
            error_message=error_message,
            error_details=error_details,
        )
        pricing = _with_runtime_identity(
            _chat_pricing(
                route.pricing,
                prompt_tokens=response.tokens_prompt,
                completion_tokens=response.tokens_completion,
            ),
            requested_model=model,
            identity=identity,
        )
        await self.trace_writer.record_cost(
            run_id=run_id,
            step_id=step_id,
            billing_basis="tokens",
            billed_quantity=response.tokens_prompt + response.tokens_completion,
            currency=pricing.currency,
            amount=pricing.amount,
            pricing_snapshot_json=pricing.snapshot,
            **identity,
            source_port="llm",
            operation="chat",
            prompt_tokens=response.tokens_prompt,
            completion_tokens=response.tokens_completion,
            total_tokens=response.tokens_prompt + response.tokens_completion,
            latency_ms=elapsed_ms,
        )

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ):
        """Stream chat completion with policy enforcement.

        Every stream that reached the provider ends in the ledger, however it
        ends: finished, failed part way (an idle timeout, a provider error, an
        outbound block), or abandoned by its consumer (a client that
        disconnects, an interaction that is canceled). Providers report usage
        only in their last chunk, so a stream that ends without it is charged
        an estimate from the prompt and from what the provider generated,
        flagged as estimated.
        """
        await self._admit(model=model, family="chat", credit_operation="chat", run_id=resolve_run_id(kwargs, self.ctx))

        if not hasattr(self.gateway, "stream_chat"):
            raise ValueError("Streaming not supported by LLM gateway")

        step = None
        step_id: str | None = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = await self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="llm",
                input_summary=f"model={model}, messages={len(messages)}",
                status="running",
            )
            # Kept as text: after a failed write rolls the session back, the
            # step instance expires and reading its id would query again.
            step_id = step.id
            await self.trace_writer.release_before_wait()

        start_time = utc_now()
        tokens_prompt = 0
        tokens_completion = 0
        # The provider reported its usage with its closing chunk.
        usage_final = False
        # The provider stream ran to its end.
        upstream_done = False
        settled = False
        model_used = None
        runtime_target: LLMRuntimeTarget | None = None
        route: _ResolvedPolicyRoute | None = None
        aiter = None
        output_preview = ""
        generated = GeneratedText()
        safety_evidence: list[dict[str, Any]] = []
        attempts: list[dict[str, Any]] = []
        outbound = (
            _OutboundStreamInspector(self, safety_evidence)
            if self.content_safety is not None and self.inspect_outbound
            else None
        )

        def observe(chunk: ChatStreamChunk) -> None:
            nonlocal tokens_prompt, tokens_completion, model_used, runtime_target, usage_final
            if chunk.tokens_prompt:
                tokens_prompt = chunk.tokens_prompt
            if chunk.tokens_completion:
                tokens_completion = chunk.tokens_completion
            if chunk.model:
                model_used = chunk.model
            if chunk.runtime_target is not None:
                runtime_target = chunk.runtime_target
            if (chunk.done or chunk.finish_reason) and (chunk.tokens_prompt or chunk.tokens_completion):
                usage_final = True
            # Counted before inspection, which may rewrite the text: the
            # provider bills for what it generated.
            generated.add(
                delta=chunk.delta,
                reasoning_delta=chunk.reasoning_delta,
                tool_call_deltas=chunk.tool_call_deltas,
                tool_calls=chunk.tool_calls,
            )

        async def release(chunk: ChatStreamChunk) -> ChatStreamChunk | None:
            # Text reaches the consumer only once it has been inspected; the
            # chunk's other signals (tool calls, usage, completion) pass as-is.
            if outbound is None:
                return chunk
            if chunk.delta:
                chunk.delta = await outbound.feed(chunk.delta)
            if chunk.done or chunk.finish_reason:
                chunk.delta = (chunk.delta or "") + await outbound.flush()
            if chunk.delta or _chunk_carries_signal(chunk):
                return chunk
            return None

        def usage() -> tuple[int, int, bool]:
            """The call's prompt and completion tokens, and whether they are estimated."""
            if usage_final or (upstream_done and (tokens_prompt or tokens_completion)):
                return tokens_prompt, tokens_completion, False
            prompt = max(tokens_prompt, estimate_prompt_tokens(messages, kwargs.get("tools")))
            completion = max(tokens_completion, generated.tokens())
            return prompt, completion, True

        async def settle(
            *,
            status: str,
            error_code: str | None = None,
            error_message: str | None = None,
            error_details: dict[str, Any] | None = None,
        ) -> None:
            """Close the step, with the call's usage in the ledger, exactly once."""
            nonlocal settled
            if settled:
                return
            settled = True
            if route is None:
                # No chunk arrived, so nothing shows the provider served the call.
                if step_id and self.trace_writer:
                    await self.trace_writer.update_step_status(
                        step_id,
                        status,
                        error_code=error_code,
                        error_message=error_message,
                        error_details=error_details,
                    )
                    await self.trace_writer.release_before_wait()
                return
            prompt, completion, estimated = usage()
            if step_id and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                upstream = model_used or model
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=upstream,
                    target=runtime_target,
                )
                await self.trace_writer.update_step_status(
                    step_id,
                    status,
                    output_summary=output_preview[:100] if output_preview else None,
                    metrics={
                        "tokens_prompt": prompt,
                        "tokens_completion": completion,
                        "latency_ms": elapsed_ms,
                        **({"usage_estimated": True} if estimated else {}),
                        **({"attempts": attempts} if attempts else {}),
                        "model": upstream,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                        **({"content_safety": safety_evidence} if safety_evidence else {}),
                    },
                    error_code=error_code,
                    error_message=error_message,
                    error_details=error_details,
                )
                pricing = _with_runtime_identity(
                    _chat_pricing(
                        route.pricing,
                        prompt_tokens=prompt,
                        completion_tokens=completion,
                    ),
                    requested_model=model,
                    identity=identity,
                )
                snapshot = (
                    {**pricing.snapshot, **_USAGE_ESTIMATE_SNAPSHOT} if estimated else pricing.snapshot
                )
                await self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step_id,
                    billing_basis="tokens",
                    billed_quantity=prompt + completion,
                    currency=pricing.currency,
                    amount=pricing.amount,
                    pricing_snapshot_json=snapshot,
                    **identity,
                    source_port="llm",
                    operation="chat",
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=prompt + completion,
                    latency_ms=elapsed_ms,
                )
                # The call is over: its step and cost are committed now, so
                # they outlive a caller that rolls its own work back (a
                # response worker that lost its lease or is draining).
                await self.trace_writer.release_before_wait()
            # After the ledger: the key's daily total must not keep the ledger
            # row from being written.
            try:
                await self._count_api_key_tokens(prompt + completion)
            except Exception:
                logger.warning("Could not add a chat stream's tokens to its API key", exc_info=True)

        async def finish(**outcome: Any) -> None:
            # The consumer may be under cancellation (a client that
            # disconnected, a task group that is closing); the provider stream
            # still closes and the ledger writes still finish, each within
            # its own bound.
            with anyio.CancelScope(shield=True):
                close = getattr(aiter, "aclose", None)
                if close is not None:
                    # Closing the provider stream ends the generation it bills for.
                    with anyio.move_on_after(_PROVIDER_CLOSE_TIMEOUT_SECONDS):
                        try:
                            await close()
                        except Exception:
                            logger.debug("Closing a provider stream failed", exc_info=True)
                with anyio.move_on_after(_SETTLE_TIMEOUT_SECONDS) as scope:
                    await settle(**outcome)
            if scope.cancelled_caught:
                logger.warning("Recording a chat stream's usage timed out", extra={"step_id": step_id})

        # A stream yields to its consumer between chunks, so this span is kept
        # off the context stack: a span attached across a yield can be resumed
        # and detached in a different task. It still covers the whole stream.
        keeps_content = await self._keeps_content()
        span = self.otel_tracer.start_span(
            "soit.llm.stream_chat",
            attributes={
                "gen_ai.operation.name": "chat",
                "gen_ai.request.model": model,
                "gen_ai.provider.name": _provider_from_model(model) or "unknown",
                "soit.tenant.id": self.ctx.tenant_id,
                "soit.workspace.id": self.ctx.workspace_id,
                "soit.run.id": resolve_run_id(kwargs, self.ctx) or "",
                "soit.step.id": step_id or "",
                "soit.llm.streaming": True,
            },
        )
        try:
            messages = await self._inspect_messages(messages, safety_evidence)
            required_capabilities = ("chat", "tools") if kwargs.get("tools") else ("chat",)
            request = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            }
            targets = await self._targets(model)
            first_chunk: ChatStreamChunk | None = None
            # A stream moves to another target only before its first chunk;
            # after that the consumer has seen output from this one.
            for index, target in enumerate(targets):
                last = index == len(targets) - 1
                try:
                    candidate = await self._resolve_call_route(target, required_capabilities)
                except KernelError as exc:
                    if last or exc.code not in _UNAVAILABLE_ROUTE_CODES:
                        raise
                    attempts.append(
                        {"model_ref": target, "outcome": "unavailable", "reason": exc.code}
                    )
                    continue
                try:
                    aiter, first_chunk = await self._open_stream(candidate, target, request)
                except Exception as exc:
                    if last or not self._fails_over(exc, candidate):
                        raise
                    attempts.append(
                        {"model_ref": target, "outcome": "failed", "reason": failure_label(exc)}
                    )
                    continue
                route = candidate
                if len(targets) > 1:
                    attempts.append({"model_ref": target, "outcome": "succeeded"})
                break
            if route is None:
                raise KernelError("MODEL_RUNTIME_NOT_FOUND", f"No model could serve: {model}")
            runtime_target = route.target

            if first_chunk is None:
                upstream_done = True
            else:
                observe(first_chunk)
                released = await release(first_chunk)
                if released is not None:
                    if released.delta and len(output_preview) < 200:
                        output_preview += released.delta
                    yield released

            while aiter is not None and not upstream_done:
                try:
                    chunk: ChatStreamChunk = await asyncio.wait_for(
                        aiter.__anext__(),
                        timeout=route.timeout_seconds,
                    )
                except StopAsyncIteration:
                    upstream_done = True
                    break
                except TimeoutError:
                    raise KernelTimeoutError(
                        f"LLM stream idle timeout after {route.timeout_seconds} seconds",
                        {"timeout_seconds": route.timeout_seconds, "model": model},
                    ) from None

                chunk.runtime_target = chunk.runtime_target or route.target
                observe(chunk)

                released = await release(chunk)
                if released is None:
                    continue
                if released.delta and len(output_preview) < 200:
                    output_preview += released.delta
                yield released

            if outbound is not None:
                # A stream that ends without a closing chunk still releases
                # whatever it held back, inspected like the rest.
                tail = await outbound.flush()
                if tail:
                    if len(output_preview) < 200:
                        output_preview += tail
                    yield ChatStreamChunk(
                        delta=tail,
                        model=model_used,
                        runtime_target=runtime_target,
                    )

            await finish(status="succeeded")
            span.set_attribute("gen_ai.response.model", model_used or model)
            span.set_attribute("gen_ai.usage.input_tokens", tokens_prompt)
            span.set_attribute("gen_ai.usage.output_tokens", tokens_completion)
        except Exception as e:
            if keeps_content:
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
            else:
                span.set_status(Status(StatusCode.ERROR, failure_label(e)))
            try:
                await finish(
                    status="failed",
                    error_code="LLM_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            except Exception:
                logger.warning(
                    "Could not record a failed chat stream",
                    exc_info=True,
                    extra={"step_id": step_id},
                )
            raise
        except (GeneratorExit, asyncio.CancelledError):
            span.set_status(Status(StatusCode.ERROR, "stream abandoned"))
            if _closing_a_dropped_generator():
                logger.warning(
                    "A chat stream was dropped without being closed; its usage is not recorded",
                    extra={"step_id": step_id},
                )
            elif upstream_done or usage_final:
                # The model had finished; only the consumer stopped early.
                try:
                    await finish(status="succeeded")
                except Exception:
                    logger.warning(
                        "Could not record a finished chat stream",
                        exc_info=True,
                        extra={"step_id": step_id},
                    )
            else:
                try:
                    await finish(
                        status="canceled",
                        error_code=STREAM_ABANDONED,
                        error_message=(
                            "The stream was closed before the model finished"
                            if route is not None
                            else "The stream was closed before the model answered"
                        ),
                    )
                except Exception:
                    logger.warning(
                        "Could not record an abandoned chat stream",
                        exc_info=True,
                        extra={"step_id": step_id},
                    )
            raise
        finally:
            span.end()

    async def embed(
        self,
        texts: list[str],
        model: str,
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Generate embeddings with policy enforcement.

        Args:
            texts: List of texts to embed.
            model: Model reference.
            **kwargs: Additional parameters.

        Returns:
            EmbeddingResponse instance.
        """
        await self._admit(model=model, family="embed", credit_operation="embed", run_id=resolve_run_id(kwargs, self.ctx))

        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = await self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="retrieval",
                input_summary=f"model={model}, texts={len(texts)}",
                status="running",
            )
            await self.trace_writer.release_before_wait()

        start_time = utc_now()
        try:
            with call_span(
                self.otel_tracer,
                "soit.llm.embed",
                keeps_content=await self._keeps_content(),
                attributes={
                    "gen_ai.operation.name": "embeddings",
                    "gen_ai.request.model": model,
                    "gen_ai.provider.name": _provider_from_model(model) or "unknown",
                    "soit.tenant.id": self.ctx.tenant_id,
                    "soit.workspace.id": self.ctx.workspace_id,
                    "soit.run.id": resolve_run_id(kwargs, self.ctx) or "",
                    "soit.step.id": step.id if step else "",
                    "soit.llm.embed.input_count": len(texts),
                },
            ) as span:
                route, response, attempts = await self._call_with_failover(
                    model,
                    ("embeddings",),
                    lambda route, target: route.port.embed(
                        texts=texts, model=target, ctx=self.ctx, **kwargs
                    ),
                    operation="LLM embed request",
                )
                response.runtime_target = response.runtime_target or route.target
                span.set_attribute("gen_ai.response.model", response.model or model)
                span.set_attribute("gen_ai.usage.input_tokens", response.tokens_used)

            await self._count_api_key_tokens(response.tokens_used or 0)

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=response.model,
                    target=response.runtime_target,
                )
                await self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "embedding_count": len(texts),
                        "latency_ms": elapsed_ms,
                        **({"attempts": attempts} if attempts else {}),
                        "model": model_used,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                pricing = _with_runtime_identity(
                    _embed_pricing(
                        route.pricing,
                        tokens_used=response.tokens_used or 0,
                    ),
                    requested_model=model,
                    identity=identity,
                )
                await self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    billing_basis="embeddings",
                    billed_quantity=len(texts),
                    currency=pricing.currency,
                    amount=pricing.amount,
                    pricing_snapshot_json=pricing.snapshot,
                    **identity,
                    source_port="llm",
                    operation="embed",
                    prompt_tokens=response.tokens_used,
                    total_tokens=response.tokens_used,
                    latency_ms=elapsed_ms,
                    embedding_count=len(texts),
                )

            return response
        except Exception as e:
            if step and self.trace_writer:
                await self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="EMBED_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise

    async def generate_image(
        self,
        prompt: str,
        model: str,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        """Generate images with policy enforcement.

        Args:
            prompt: Text prompt describing the image.
            model: Model reference.
            n: Number of images to generate.
            size: Optional image size hint.
            **kwargs: Additional parameters.

        Returns:
            ImageGenerationResponse instance.
        """
        await self._admit(model=model, family="image", credit_operation="generate_image", run_id=resolve_run_id(kwargs, self.ctx))

        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = await self.trace_writer.create_step(
                run_id=run_id,
                step_type="llm",
                input_summary=f"model={model}, images={n}, prompt={prompt[:200]}",
                status="running",
            )
            await self.trace_writer.release_before_wait()

        start_time = utc_now()
        route: _ResolvedPolicyRoute | None = None
        target = model
        asked = False
        try:
            route, target, attempts = await self._first_available_route(
                model,
                ("image_generation",),
                timeout_fallback=self.image_timeout_seconds,
                max_retries_cap=self.image_max_retries,
            )
            # Refuse against what the model declared before the provider is
            # called, so an impossible request is never billed.
            validate_image_request(
                route.image_capabilities,
                model=target,
                size=size,
                background=kwargs.get("background"),
                seed=kwargs.get("seed"),
            )
            await self._note_image_call(step, route=route, model=model, target=target, images=n, edit=False)
            asked = True
            with call_span(
                self.otel_tracer,
                "soit.llm.generate_image",
                keeps_content=await self._keeps_content(),
                attributes={
                    "gen_ai.operation.name": "image_generation",
                    "gen_ai.request.model": model,
                    "gen_ai.provider.name": _provider_from_model(model) or "unknown",
                    "soit.tenant.id": self.ctx.tenant_id,
                    "soit.workspace.id": self.ctx.workspace_id,
                    "soit.run.id": resolve_run_id(kwargs, self.ctx) or "",
                    "soit.step.id": step.id if step else "",
                    "soit.llm.image.requested_count": n,
                },
            ) as span:
                response = await self._run_call(
                    lambda: route.port.generate_image(
                        prompt=prompt, model=target, n=n, size=size, ctx=self.ctx, **kwargs
                    ),
                    timeout_factory=lambda: KernelTimeoutError(
                        f"LLM image request timed out after {route.timeout_seconds} seconds",
                        {"timeout_seconds": route.timeout_seconds, "model": model},
                    ),
                    timeout_seconds=route.timeout_seconds,
                    max_retries=route.max_retries,
                    retry_backoff=route.retry_backoff,
                    retryable_status_codes=route.retryable_status_codes,
                )
                response.runtime_target = response.runtime_target or route.target
                span.set_attribute("gen_ai.response.model", response.model or model)
                span.set_attribute(
                    "soit.llm.image.generated_count",
                    len(response.images),
                )

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                image_count = len(response.images)
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=response.model,
                    target=response.runtime_target,
                )
                await self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "image_count": image_count,
                        "latency_ms": elapsed_ms,
                        **({"attempts": attempts} if attempts else {}),
                        "model": response.model or model,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                pricing = _with_runtime_identity(
                    _image_pricing(
                        route.pricing,
                        image_count=image_count,
                        size=size,
                        quality=kwargs.get("quality"),
                        steps=kwargs.get("steps"),
                    ),
                    requested_model=model,
                    identity=identity,
                )
                await self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    billing_basis="images",
                    billed_quantity=image_count,
                    currency=pricing.currency,
                    amount=pricing.amount,
                    pricing_snapshot_json=pricing.snapshot,
                    **identity,
                    source_port="llm",
                    operation="generate_image",
                    latency_ms=elapsed_ms,
                    request_count=n,
                )

            return response
        except Exception as e:
            if step and self.trace_writer:
                charged = asked and route is not None and isinstance(e, KernelTimeoutError)
                if charged:
                    await self._charge_unanswered_images(
                        step.id,
                        route=route,
                        model=model,
                        images=n,
                        size=size,
                        operation="generate_image",
                        run_id=resolve_run_id(kwargs, self.ctx),
                        elapsed_ms=int((utc_now() - start_time).total_seconds() * 1000),
                    )
                await self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    metrics={"usage_estimated": True} if charged else None,
                    error_code="IMAGE_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise

    async def _note_image_call(
        self,
        step: Any,
        *,
        route: _ResolvedPolicyRoute,
        model: str,
        target: str,
        images: int,
        edit: bool,
    ) -> None:
        """Make durable, before the provider is asked, what the call asks for.

        If its answer never comes, the gateway charges it on a timeout; if the
        process making the call is lost, the image job reaper tells the charge
        from what this writes on the step: the count, the model asked for, and
        the target and provider serving it.
        """
        if not step or not self.trace_writer:
            return
        served_by = route.target
        await self.trace_writer.update_step_status(
            step.id,
            "running",
            metrics={
                "requested_images": images,
                "image_edit": edit,
                "model": model,
                "model_ref": target,
                "provider_id": served_by.provider_id if served_by else None,
                "provider_slug": served_by.provider_slug if served_by else None,
                "provider_kind": served_by.provider_kind if served_by else None,
            },
        )
        await self.trace_writer.release_before_wait()

    async def _charge_unanswered_images(
        self,
        step_id: str,
        *,
        route: _ResolvedPolicyRoute,
        model: str,
        images: int,
        size: str | None,
        operation: str,
        run_id: str | None,
        elapsed_ms: int,
    ) -> None:
        """Charge an image call that timed out: the provider may still bill it."""
        assert self.trace_writer is not None
        pricing, identity = unconfirmed_image_charge(
            route.pricing,
            requested_model=model,
            target=route.target,
            images=images,
            size=size,
        )
        await self.trace_writer.record_cost(
            run_id=run_id,
            step_id=step_id,
            billing_basis="images",
            billed_quantity=images,
            currency=pricing.currency,
            amount=pricing.amount,
            pricing_snapshot_json=pricing.snapshot,
            **identity,
            source_port="llm",
            operation=operation,
            latency_ms=elapsed_ms,
            request_count=images,
        )

    async def check_image_request(
        self,
        model: str,
        *,
        operation: str,
        n: int = 1,
        size: str | None = None,
        has_mask: bool = False,
        **options: Any,
    ) -> None:
        """Refuse, before a run opens, an image request the call would refuse.

        Picks the target the call would, the first available one, and applies
        the checks the call makes before the provider: the credential's model
        list, the model's declared traits, and what its route can carry. The
        route is described, not connected: no secret is resolved and nothing
        reaches the network. It admits, records and bills nothing, so an
        asynchronous job is refused on submission instead of failing after it
        was accepted. Anything else wrong with the route is left to the call,
        which reports it as it always has, on a run.
        """
        self._check_model_allowed(model)
        try:
            port, image_capabilities, target = await self._first_described_route(
                model, ("image_edit",) if operation == "edit" else ("image_generation",)
            )
        except KernelError:
            return
        validate_image_request(
            image_capabilities,
            model=target,
            size=size,
            has_mask=has_mask,
            background=options.get("background"),
            seed=options.get("seed"),
        )
        check = getattr(port, "check_image_request", None)
        if check is not None:
            await check(target, operation=operation, n=n, size=size, has_mask=has_mask, **options)

    async def _first_described_route(
        self, model: str, required_capabilities: tuple[str, ...]
    ) -> tuple[Any, dict[str, Any], str]:
        """The port, declared image traits and target an image call would pick.

        Mirrors ``_first_available_route`` through the gateway's
        ``describe_route``, which connects nothing. A gateway without one is
        its own route, as in ``_resolve_call_route``.
        """
        describer = getattr(type(self.gateway), "describe_route", None)
        targets = await self._targets(model)
        for index, target in enumerate(targets):
            if describer is None:
                return self.gateway, {}, target
            try:
                route = await describer(self.gateway, target, self.ctx, required_capabilities)
            except KernelError as exc:
                if index == len(targets) - 1 or exc.code not in _UNAVAILABLE_ROUTE_CODES:
                    raise
                continue
            return route.port, getattr(route, "image_capabilities", None) or {}, target
        raise KernelError("MODEL_RUNTIME_NOT_FOUND", f"No model could serve: {model}")

    async def edit_image(
        self,
        image: bytes,
        prompt: str,
        model: str,
        mask: bytes | None = None,
        n: int = 1,
        size: str | None = None,
        **kwargs: Any,
    ) -> ImageGenerationResponse:
        """Edit an image with policy enforcement.

        Deliberately the same chain as ``generate_image`` - one rate limit, one
        daily quota, one credit guard, one trace step, one cost row - because an
        edit is the same kind of spend as a generation. Only the capability
        token and the operation name differ, so an edit appears in the ledger as
        its own operation without a second governance mechanism existing.

        Args:
            image: Source image bytes.
            prompt: What the edited region should become.
            model: Model reference.
            mask: Optional selection; white marks the region to edit.
            n: Number of images to return.
            size: Optional output size.
            **kwargs: Additional parameters.

        Returns:
            ImageGenerationResponse instance.
        """
        await self._admit(model=model, family="image", credit_operation="edit_image", run_id=resolve_run_id(kwargs, self.ctx))

        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            masked = "yes" if mask else "no"
            step = await self.trace_writer.create_step(
                run_id=run_id,
                step_type="llm",
                input_summary=(
                    f"model={model}, images={n}, mask={masked}, prompt={prompt[:200]}"
                ),
            )
            await self.trace_writer.update_step_status(step.id, "running")
            await self.trace_writer.release_before_wait()

        start_time = utc_now()
        route: _ResolvedPolicyRoute | None = None
        target = model
        asked = False
        try:
            route, target, attempts = await self._first_available_route(
                model,
                ("image_edit",),
                timeout_fallback=self.image_timeout_seconds,
                max_retries_cap=self.image_max_retries,
            )
            validate_image_request(
                route.image_capabilities,
                model=target,
                size=size,
                has_mask=mask is not None,
                background=kwargs.get("background"),
                seed=kwargs.get("seed"),
            )
            await self._note_image_call(step, route=route, model=model, target=target, images=n, edit=True)
            asked = True
            with call_span(
                self.otel_tracer,
                "soit.llm.edit_image",
                keeps_content=await self._keeps_content(),
                attributes={
                    "gen_ai.operation.name": "image_edit",
                    "gen_ai.request.model": model,
                    "gen_ai.provider.name": _provider_from_model(model) or "unknown",
                    "soit.tenant.id": self.ctx.tenant_id,
                    "soit.workspace.id": self.ctx.workspace_id,
                    "soit.run.id": resolve_run_id(kwargs, self.ctx) or "",
                    "soit.step.id": step.id if step else "",
                    "soit.llm.image.requested_count": n,
                    "soit.llm.image.masked": mask is not None,
                },
            ) as span:
                response = await self._run_call(
                    lambda: route.port.edit_image(
                        image=image,
                        prompt=prompt,
                        model=target,
                        mask=mask,
                        n=n,
                        size=size,
                        ctx=self.ctx,
                        **kwargs,
                    ),
                    timeout_factory=lambda: KernelTimeoutError(
                        f"LLM image edit timed out after {route.timeout_seconds} seconds",
                        {"timeout_seconds": route.timeout_seconds, "model": model},
                    ),
                    timeout_seconds=route.timeout_seconds,
                    max_retries=route.max_retries,
                    retry_backoff=route.retry_backoff,
                    retryable_status_codes=route.retryable_status_codes,
                )
                response.runtime_target = response.runtime_target or route.target
                span.set_attribute("gen_ai.response.model", response.model or model)
                span.set_attribute(
                    "soit.llm.image.generated_count",
                    len(response.images),
                )

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                image_count = len(response.images)
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=response.model,
                    target=response.runtime_target,
                )
                await self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "image_count": image_count,
                        "latency_ms": elapsed_ms,
                        **({"attempts": attempts} if attempts else {}),
                        "model": response.model or model,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                pricing = _with_runtime_identity(
                    _image_pricing(
                        route.pricing,
                        image_count=image_count,
                        size=size,
                        quality=kwargs.get("quality"),
                        steps=kwargs.get("steps"),
                    ),
                    requested_model=model,
                    identity=identity,
                )
                await self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    billing_basis="images",
                    billed_quantity=image_count,
                    currency=pricing.currency,
                    amount=pricing.amount,
                    pricing_snapshot_json=pricing.snapshot,
                    **identity,
                    source_port="llm",
                    operation="edit_image",
                    latency_ms=elapsed_ms,
                    request_count=n,
                )

            return response
        except Exception as e:
            if step and self.trace_writer:
                charged = asked and route is not None and isinstance(e, KernelTimeoutError)
                if charged:
                    await self._charge_unanswered_images(
                        step.id,
                        route=route,
                        model=model,
                        images=n,
                        size=size,
                        operation="edit_image",
                        run_id=resolve_run_id(kwargs, self.ctx),
                        elapsed_ms=int((utc_now() - start_time).total_seconds() * 1000),
                    )
                await self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    metrics={"usage_estimated": True} if charged else None,
                    error_code="IMAGE_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise

    async def rerank(
        self,
        query: str,
        documents: list[str],
        model: str,
        top_n: int | None = None,
        **kwargs: Any,
    ) -> RerankResponse:
        """Rerank documents with policy enforcement.

        Args:
            query: Query text.
            documents: List of document texts.
            model: Model reference.
            top_n: Number of top results.
            **kwargs: Additional parameters.

        Returns:
            RerankResponse instance.
        """
        await self._admit(model=model, family="rerank", credit_operation="rerank", run_id=resolve_run_id(kwargs, self.ctx))

        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = await self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="rerank",
                input_summary=f"model={model}, documents={len(documents)}",
                status="running",
            )
            await self.trace_writer.release_before_wait()

        start_time = utc_now()
        try:
            with call_span(
                self.otel_tracer,
                "soit.llm.rerank",
                keeps_content=await self._keeps_content(),
                attributes={
                    "gen_ai.operation.name": "rerank",
                    "gen_ai.request.model": model,
                    "gen_ai.provider.name": _provider_from_model(model) or "unknown",
                    "soit.tenant.id": self.ctx.tenant_id,
                    "soit.workspace.id": self.ctx.workspace_id,
                    "soit.run.id": resolve_run_id(kwargs, self.ctx) or "",
                    "soit.step.id": step.id if step else "",
                    "soit.llm.rerank.document_count": len(documents),
                    "soit.llm.rerank.top_n": top_n or len(documents),
                },
            ) as span:
                route, response, attempts = await self._call_with_failover(
                    model,
                    ("rerank",),
                    lambda route, target: route.port.rerank(
                        query=query,
                        documents=documents,
                        model=target,
                        top_n=top_n,
                        ctx=self.ctx,
                        **kwargs,
                    ),
                    operation="LLM rerank request",
                )
                response.runtime_target = response.runtime_target or route.target
                span.set_attribute("gen_ai.response.model", response.model or model)
                span.set_attribute("gen_ai.usage.input_tokens", response.tokens_used)

            await self._count_api_key_tokens(response.tokens_used or 0)

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=response.model,
                    target=response.runtime_target,
                )
                await self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "rerank_count": len(documents),
                        "top_n": top_n or len(documents),
                        "latency_ms": elapsed_ms,
                        **({"attempts": attempts} if attempts else {}),
                        "model": model_used,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                pricing = _with_runtime_identity(
                    _rerank_pricing(
                        route.pricing,
                        searches=len(documents),
                        tokens_used=response.tokens_used or 0,
                    ),
                    requested_model=model,
                    identity=identity,
                )
                await self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    billing_basis="rerank",
                    billed_quantity=len(documents),
                    currency=pricing.currency,
                    amount=pricing.amount,
                    pricing_snapshot_json=pricing.snapshot,
                    **identity,
                    source_port="llm",
                    operation="rerank",
                    prompt_tokens=response.tokens_used,
                    total_tokens=response.tokens_used,
                    latency_ms=elapsed_ms,
                    rerank_count=len(documents),
                )

            return response
        except Exception as e:
            if step and self.trace_writer:
                await self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="RERANK_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise
