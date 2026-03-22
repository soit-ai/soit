""" policy

LLM port policies: timeout/retry/rate-limit/audit.
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from app.kernel.contracts.context import RequestContext
from app.kernel.ports.llm.interface import (
    LLMPort,
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    EmbeddingResponse,
    RerankResponse,
)
from app.kernel.ports.common.rate_limiter import RateLimiter
from app.kernel.ports.common.audit import log_gateway_request
from app.kernel.trace.writer import TraceWriter
from app.kernel.commons.time import utc_now
from app.kernel.commons.errors import TimeoutError, KernelError

def _resolve_run_id(kwargs: Dict[str, Any], ctx: RequestContext) -> str:
    """Resolve run_id for trace emission.

    When trace_writer is enabled, run_id must be present. We allow reading from ctx (best-effort)
    to support propagation via execution context.
    """
    run_id = kwargs.get("run_id") or getattr(ctx, "run_id", None)
    return str(run_id) if run_id else ""


def _error_details(exc: Exception) -> Dict[str, Any]:
    details: Dict[str, Any] = {"error_type": type(exc).__name__}
    if isinstance(exc, KernelError):
        details["code"] = exc.code
        details.update(exc.details or {})
    else:
        details["detail"] = str(exc)
    return details


def _provider_from_model(model_ref: Optional[str]) -> Optional[str]:
    if not model_ref:
        return None
    if model_ref.startswith("model:"):
        parts = model_ref.split(":")
        if len(parts) >= 2:
            return parts[1]
    return None

class LLMPolicyGateway(LLMPort):
    """LLM port with policy enforcement."""
    
    def __init__(
        self,
        gateway: LLMPort,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
        timeout_seconds: int = 60,
        max_retries: int = 3,
        rate_limit_per_minute: Optional[int] = None,
        daily_quota: Optional[int] = None,
        rate_limiter: Optional[RateLimiter] = None,
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
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
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
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_type="llm",
                input_summary=f"model={model}, messages={len(messages)}",
            )
            self.trace_writer.update_step_status(step.id, "running")
        
        start_time = utc_now()
        try:
            # Apply retry policy with timeout
            @retry(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=2, max=10),
            )
            async def _chat_with_retry():
                return await self.gateway.chat(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
            
            # Apply timeout
            try:
                response = await asyncio.wait_for(
                    _chat_with_retry(),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"LLM chat request timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "model": model}
                )
            
            # Update trace
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    output_summary=response.text[:100] if response.text else None,
                    metrics={
                        "tokens_prompt": response.tokens_prompt,
                        "tokens_completion": response.tokens_completion,
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="tokens",
                    quantity=response.tokens_prompt + response.tokens_completion,
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                    prompt_tokens=response.tokens_prompt,
                    completion_tokens=response.tokens_completion,
                    total_tokens=response.tokens_prompt + response.tokens_completion,
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="LLM_ERROR",
                    error_message=str(e),
                    error_details=_error_details(e),
                )
            raise

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
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
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_type="llm",
                input_summary=f"model={model}, messages={len(messages)}",
            )
            self.trace_writer.update_step_status(step.id, "running")

        start_time = utc_now()
        tokens_prompt = 0
        tokens_completion = 0
        finish_reason = None
        model_used = None
        output_preview = ""

        import inspect
        stream = self.gateway.stream_chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        if inspect.isawaitable(stream):
            stream = await stream

        try:
            aiter = stream.__aiter__()
            while True:
                try:
                    chunk: ChatStreamChunk = await asyncio.wait_for(
                        aiter.__anext__(),
                        timeout=self.timeout_seconds,
                    )
                except StopAsyncIteration:
                    break

                if chunk.delta and len(output_preview) < 200:
                    output_preview += chunk.delta

                if chunk.tokens_prompt:
                    tokens_prompt = chunk.tokens_prompt
                if chunk.tokens_completion:
                    tokens_completion = chunk.tokens_completion
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                if chunk.model:
                    model_used = chunk.model

                yield chunk

            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = model_used or model
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    output_summary=output_preview[:100] if output_preview else None,
                    metrics={
                        "tokens_prompt": tokens_prompt,
                        "tokens_completion": tokens_completion,
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="tokens",
                    quantity=tokens_prompt + tokens_completion,
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                    prompt_tokens=tokens_prompt,
                    completion_tokens=tokens_completion,
                    total_tokens=tokens_prompt + tokens_completion,
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                )
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="LLM_ERROR",
                    error_message=str(e),
                    error_details=_error_details(e),
                )
            raise
    
    async def embed(
        self,
        texts: List[str],
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
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_type="retrieval",
                input_summary=f"model={model}, texts={len(texts)}",
            )
            self.trace_writer.update_step_status(step.id, "running")
        
        start_time = utc_now()
        try:
            @retry(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=2, max=10),
            )
            async def _embed_with_retry():
                return await self.gateway.embed(texts=texts, model=model, **kwargs)
            
            # Apply timeout
            try:
                response = await asyncio.wait_for(
                    _embed_with_retry(),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"LLM embed request timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "model": model}
                )
            
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "embedding_count": len(texts),
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="embeddings",
                    quantity=len(texts),
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="EMBED_ERROR",
                    error_message=str(e),
                    error_details=_error_details(e),
                )
            raise
    
    async def rerank(
        self,
        query: str,
        documents: List[str],
        model: str,
        top_n: Optional[int] = None,
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
            run_id = _resolve_run_id(kwargs, self.ctx)
            if not run_id:
                raise ValueError("run_id is required when trace_writer is enabled")
            step = self.trace_writer.create_step(
                run_id=_resolve_run_id(kwargs, self.ctx),
                step_type="rerank",
                input_summary=f"model={model}, documents={len(documents)}",
            )
            self.trace_writer.update_step_status(step.id, "running")
        
        start_time = utc_now()
        try:
            @retry(
                stop=stop_after_attempt(self.max_retries),
                wait=wait_exponential(multiplier=1, min=2, max=10),
            )
            async def _rerank_with_retry():
                return await self.gateway.rerank(
                    query=query,
                    documents=documents,
                    model=model,
                    top_n=top_n,
                    **kwargs,
                )
            
            # Apply timeout
            try:
                response = await asyncio.wait_for(
                    _rerank_with_retry(),
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    f"LLM rerank request timed out after {self.timeout_seconds} seconds",
                    {"timeout_seconds": self.timeout_seconds, "model": model}
                )
            
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                model_used = response.model or model
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "rerank_count": len(documents),
                        "top_n": top_n or len(documents),
                        "latency_ms": elapsed_ms,
                        "model": model_used,
                    },
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="rerank",
                    quantity=len(documents),
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                )
                self.trace_writer.record_cost(
                    run_id=_resolve_run_id(kwargs, self.ctx),
                    step_id=step.id,
                    unit="ms",
                    quantity=elapsed_ms,
                    provider=_provider_from_model(model_used),
                    model_ref=model_used,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="RERANK_ERROR",
                    error_message=str(e),
                    error_details=_error_details(e),
                )
            raise
