""" policy

LLM port policies: timeout/retry/rate-limit/audit.
"""

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Tracer

from app.kernel.commons.errors import KernelError
from app.kernel.commons.errors import TimeoutError as KernelTimeoutError
from app.kernel.commons.time import utc_now
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.common.policy import (
    error_details,
    resolve_run_id,
)
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.llm.interface import (
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    LLMPort,
    LLMRuntimeTarget,
    RerankResponse,
)
from app.kernel.runtime.runs.writer import TraceWriter


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


@dataclass(frozen=True)
class _ResolvedPolicyRoute:
    port: LLMPort
    target: LLMRuntimeTarget | None
    timeout_seconds: float
    max_retries: int
    retry_backoff: str
    retryable_status_codes: tuple[int, ...]


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
    ):
        """Initialize policy gateway.

        Args:
            gateway: Underlying LLM port.
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            timeout_seconds: Request timeout in seconds.
            max_retries: Maximum retry attempts.
            rate_limit_per_minute: Optional rate limit per minute.
            daily_quota: Optional daily request quota.
            rate_limiter: Optional rate limiter instance.
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

    async def _resolve_call_route(self, model: str) -> _ResolvedPolicyRoute:
        resolver = getattr(type(self.gateway), "resolve_route", None)
        if resolver is None:
            return _ResolvedPolicyRoute(
                port=self.gateway,
                target=None,
                timeout_seconds=self.timeout_seconds,
                max_retries=self.max_retries,
                retry_backoff=self.retry_backoff,
                retryable_status_codes=self.retryable_status_codes,
            )
        route = resolver(self.gateway, model, self.ctx)
        if inspect.isawaitable(route):
            route = await route
        return _ResolvedPolicyRoute(
            port=route.port,
            target=route.target,
            timeout_seconds=route.timeout_seconds or self.timeout_seconds,
            max_retries=self.max_retries if route.max_retries is None else route.max_retries,
            retry_backoff=route.retry_backoff,
            retryable_status_codes=route.retryable_status_codes,
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

    async def _check_daily_quota(self, *, key_suffix: str) -> None:
        if not self.daily_quota:
            return
        quota_key = f"quota:llm:{key_suffix}:{self.ctx.tenant_id}:{self.ctx.workspace_id}"
        await self.rate_limiter.check_rate_limit(
            key=quota_key,
            limit=self.daily_quota,
            window_seconds=86400,
        )

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
        # Rate limiting check
        if self.rate_limit_per_minute:
            rate_limit_key = f"llm:chat:{self.ctx.tenant_id}:{self.ctx.workspace_id}:{self.ctx.user_id}"
            await self.rate_limiter.check_rate_limit(
                key=rate_limit_key,
                limit=self.rate_limit_per_minute,
                window_seconds=60,
            )
        await self._check_daily_quota(key_suffix="chat")

        # Audit log
        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="llm",
                input_summary=f"model={model}, messages={len(messages)}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        try:
            route = await self._resolve_call_route(model)
            with self.otel_tracer.start_as_current_span(
                "soit.llm.chat",
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
                response = await self._run_call(
                    lambda: route.port.chat(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        ctx=self.ctx,
                        **kwargs,
                    ),
                    timeout_factory=lambda: KernelTimeoutError(
                        f"LLM chat request timed out after {route.timeout_seconds} seconds",
                        {"timeout_seconds": route.timeout_seconds, "model": model},
                    ),
                    timeout_seconds=route.timeout_seconds,
                    max_retries=route.max_retries,
                    retry_backoff=route.retry_backoff,
                    retryable_status_codes=route.retryable_status_codes,
                )
                response.runtime_target = response.runtime_target or route.target
                span.set_attribute("gen_ai.response.model", response.model or model)
                span.set_attribute("gen_ai.usage.input_tokens", response.tokens_prompt)
                span.set_attribute("gen_ai.usage.output_tokens", response.tokens_completion)

            # Update trace
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=response.model,
                    target=response.runtime_target,
                )
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    output_summary=response.text[:100] if response.text else None,
                    metrics={
                        "tokens_prompt": response.tokens_prompt,
                        "tokens_completion": response.tokens_completion,
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="tokens",
                    quantity=response.tokens_prompt + response.tokens_completion,
                    **identity,
                    prompt_tokens=response.tokens_prompt,
                    completion_tokens=response.tokens_completion,
                    total_tokens=response.tokens_prompt + response.tokens_completion,
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    **identity,
                )

            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="LLM_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ):
        """Stream chat completion with policy enforcement."""
        if self.rate_limit_per_minute:
            rate_limit_key = f"llm:chat:{self.ctx.tenant_id}:{self.ctx.workspace_id}:{self.ctx.user_id}"
            await self.rate_limiter.check_rate_limit(
                key=rate_limit_key,
                limit=self.rate_limit_per_minute,
                window_seconds=60,
            )
        await self._check_daily_quota(key_suffix="chat")

        if not hasattr(self.gateway, "stream_chat"):
            raise ValueError("Streaming not supported by LLM gateway")

        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="llm",
                input_summary=f"model={model}, messages={len(messages)}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        tokens_prompt = 0
        tokens_completion = 0
        model_used = None
        runtime_target: LLMRuntimeTarget | None = None
        output_preview = ""

        try:
            route = await self._resolve_call_route(model)
            runtime_target = route.target
            first_chunk: ChatStreamChunk | None = None
            aiter = None
            for attempt in range(route.max_retries + 1):
                try:
                    stream = route.port.stream_chat(
                        messages=messages,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        ctx=self.ctx,
                        **kwargs,
                    )
                    if inspect.isawaitable(stream):
                        stream = await asyncio.wait_for(stream, timeout=route.timeout_seconds)
                    aiter = stream.__aiter__()
                    first_chunk = await asyncio.wait_for(
                        aiter.__anext__(),
                        timeout=route.timeout_seconds,
                    )
                    first_chunk.runtime_target = first_chunk.runtime_target or route.target
                    break
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    if attempt >= route.max_retries:
                        raise KernelTimeoutError(
                            f"LLM stream request timed out after {route.timeout_seconds} seconds",
                            {"timeout_seconds": route.timeout_seconds, "model": model},
                        ) from None
                except Exception as exc:
                    if attempt >= route.max_retries or not self._is_retryable(
                        exc,
                        route.retryable_status_codes,
                    ):
                        raise
                if route.retry_backoff != "none" and self.retry_backoff_base_seconds:
                    multiplier = 2**attempt if route.retry_backoff == "exponential" else 1
                    await asyncio.sleep(
                        min(self.retry_backoff_base_seconds * multiplier, 5.0)
                    )

            if first_chunk is not None:
                if first_chunk.delta and len(output_preview) < 200:
                    output_preview += first_chunk.delta
                tokens_prompt = first_chunk.tokens_prompt or tokens_prompt
                tokens_completion = first_chunk.tokens_completion or tokens_completion
                model_used = first_chunk.model or model_used
                yield first_chunk

            while True:
                if aiter is None or first_chunk is None:
                    break
                try:
                    chunk: ChatStreamChunk = await asyncio.wait_for(
                        aiter.__anext__(),
                        timeout=route.timeout_seconds,
                    )
                except StopAsyncIteration:
                    break
                except TimeoutError:
                    raise KernelTimeoutError(
                        f"LLM stream idle timeout after {route.timeout_seconds} seconds",
                        {"timeout_seconds": route.timeout_seconds, "model": model},
                    ) from None

                chunk.runtime_target = chunk.runtime_target or route.target

                if chunk.delta and len(output_preview) < 200:
                    output_preview += chunk.delta

                if chunk.tokens_prompt:
                    tokens_prompt = chunk.tokens_prompt
                if chunk.tokens_completion:
                    tokens_completion = chunk.tokens_completion
                if chunk.model:
                    model_used = chunk.model
                if chunk.runtime_target is not None:
                    runtime_target = chunk.runtime_target

                yield chunk

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = model_used or model
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=model_used,
                    target=runtime_target,
                )
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    output_summary=output_preview[:100] if output_preview else None,
                    metrics={
                        "tokens_prompt": tokens_prompt,
                        "tokens_completion": tokens_completion,
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="tokens",
                    quantity=tokens_prompt + tokens_completion,
                    **identity,
                    prompt_tokens=tokens_prompt,
                    completion_tokens=tokens_completion,
                    total_tokens=tokens_prompt + tokens_completion,
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    **identity,
                )
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="LLM_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise

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
        # Rate limiting check
        if self.rate_limit_per_minute:
            rate_limit_key = f"llm:embed:{self.ctx.tenant_id}:{self.ctx.workspace_id}:{self.ctx.user_id}"
            await self.rate_limiter.check_rate_limit(
                key=rate_limit_key,
                limit=self.rate_limit_per_minute,
                window_seconds=60,
            )
        await self._check_daily_quota(key_suffix="embed")

        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="retrieval",
                input_summary=f"model={model}, texts={len(texts)}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        try:
            route = await self._resolve_call_route(model)
            response = await self._run_call(
                lambda: route.port.embed(texts=texts, model=model, ctx=self.ctx, **kwargs),
                timeout_factory=lambda: KernelTimeoutError(
                    f"LLM embed request timed out after {route.timeout_seconds} seconds",
                    {"timeout_seconds": route.timeout_seconds, "model": model}
                ),
                timeout_seconds=route.timeout_seconds,
                max_retries=route.max_retries,
                retry_backoff=route.retry_backoff,
                retryable_status_codes=route.retryable_status_codes,
            )
            response.runtime_target = response.runtime_target or route.target

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=response.model,
                    target=response.runtime_target,
                )
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "embedding_count": len(texts),
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="embeddings",
                    quantity=len(texts),
                    **identity,
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    **identity,
                )

            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="EMBED_ERROR",
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
        # Rate limiting check
        if self.rate_limit_per_minute:
            rate_limit_key = f"llm:rerank:{self.ctx.tenant_id}:{self.ctx.workspace_id}:{self.ctx.user_id}"
            await self.rate_limiter.check_rate_limit(
                key=rate_limit_key,
                limit=self.rate_limit_per_minute,
                window_seconds=60,
            )
        await self._check_daily_quota(key_suffix="rerank")

        step = None
        if self.trace_writer:
            run_id = resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=resolve_run_id(kwargs, self.ctx),
                step_type="rerank",
                input_summary=f"model={model}, documents={len(documents)}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        try:
            route = await self._resolve_call_route(model)
            response = await self._run_call(
                lambda: route.port.rerank(
                    query=query,
                    documents=documents,
                    model=model,
                    top_n=top_n,
                    ctx=self.ctx,
                    **kwargs,
                ),
                timeout_factory=lambda: KernelTimeoutError(
                    f"LLM rerank request timed out after {route.timeout_seconds} seconds",
                    {"timeout_seconds": route.timeout_seconds, "model": model}
                ),
                timeout_seconds=route.timeout_seconds,
                max_retries=route.max_retries,
                retry_backoff=route.retry_backoff,
                retryable_status_codes=route.retryable_status_codes,
            )
            response.runtime_target = response.runtime_target or route.target

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                identity = _runtime_cost_fields(
                    requested_model=model,
                    upstream_model=response.model,
                    target=response.runtime_target,
                )
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "rerank_count": len(documents),
                        "top_n": top_n or len(documents),
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                        "model_ref": identity["model_ref"],
                        "provider_id": identity["provider_id"],
                        "provider_slug": identity["provider_slug"],
                        "provider_kind": identity["provider_kind"],
                        "upstream_model": identity["upstream_model"],
                    },
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="rerank",
                    quantity=len(documents),
                    **identity,
                )
                self.trace_writer.record_cost(
                    run_id=resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    **identity,
                )

            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="RERANK_ERROR",
                    error_message=str(e),
                    error_details=error_details(e),
                )
            raise
