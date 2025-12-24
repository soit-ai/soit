""" policy

LLM gateway policies: timeout/retry/rate-limit/audit.
"""

from typing import Optional, Dict, Any
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

from app.kernel.contracts.context import RequestContext
from app.kernel.gateways.llm.interface import LLMGateway, ChatMessage, ChatResponse, EmbeddingResponse, RerankResponse
from app.kernel.trace.writer import TraceWriter
from app.kernel.commons.time import utc_now


class LLMPolicyGateway(LLMGateway):
    """LLM gateway with policy enforcement."""
    
    def __init__(
        self,
        gateway: LLMGateway,
        ctx: RequestContext,
        trace_writer: Optional[TraceWriter] = None,
        timeout_seconds: int = 60,
        max_retries: int = 3,
        rate_limit_per_minute: Optional[int] = None,
    ):
        """Initialize policy gateway.
        
        Args:
            gateway: Underlying LLM gateway.
            ctx: Request context.
            trace_writer: Optional trace writer for audit.
            timeout_seconds: Request timeout in seconds.
            max_retries: Maximum retry attempts.
            rate_limit_per_minute: Optional rate limit per minute.
        """
        self.gateway = gateway
        self.ctx = ctx
        self.trace_writer = trace_writer
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.rate_limit_per_minute = rate_limit_per_minute
    
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
        # Rate limiting check (placeholder - implement Redis-based rate limiter)
        # Audit log
        step = None
        if self.trace_writer:
            step = self.trace_writer.create_step(
                run_id=kwargs.get("run_id", ""),
                step_type="llm",
                input_summary=f"model={model}, messages={len(messages)}",
            )
            self.trace_writer.update_step_status(step.id, "running")
        
        start_time = utc_now()
        try:
            # Apply retry policy
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
            
            response = await _chat_with_retry()
            
            # Update trace
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    output_summary=response.text[:100] if response.text else None,
                    metrics={
                        "tokens_prompt": response.tokens_prompt,
                        "tokens_completion": response.tokens_completion,
                        "latency_ms": elapsed_ms,
                        "model": response.model or model,
                    },
                )
                # Update cost
                self.trace_writer.update_cost(
                    run_id=kwargs.get("run_id", ""),
                    tokens_prompt=response.tokens_prompt,
                    tokens_completion=response.tokens_completion,
                    ms_total=elapsed_ms,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="LLM_ERROR",
                    error_message=str(e),
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
        step = None
        if self.trace_writer:
            step = self.trace_writer.create_step(
                run_id=kwargs.get("run_id", ""),
                step_type="retrieve",
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
            
            response = await _embed_with_retry()
            
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "embedding_count": len(texts),
                        "latency_ms": elapsed_ms,
                        "model": response.model or model,
                    },
                )
                self.trace_writer.update_cost(
                    run_id=kwargs.get("run_id", ""),
                    embedding_count=len(texts),
                    ms_total=elapsed_ms,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="EMBED_ERROR",
                    error_message=str(e),
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
        step = None
        if self.trace_writer:
            step = self.trace_writer.create_step(
                run_id=kwargs.get("run_id", ""),
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
            
            response = await _rerank_with_retry()
            
            if step and self.trace_writer:
                elapsed_ms = int((utc_now() - start_time).total_seconds() * 1000)
                self.trace_writer.update_step_status(
                    step.id,
                    "succeeded",
                    metrics={
                        "tokens_used": response.tokens_used,
                        "rerank_count": len(documents),
                        "top_n": top_n or len(documents),
                        "latency_ms": elapsed_ms,
                        "model": response.model or model,
                    },
                )
                self.trace_writer.update_cost(
                    run_id=kwargs.get("run_id", ""),
                    rerank_count=len(documents),
                    ms_total=elapsed_ms,
                )
            
            return response
        except Exception as e:
            if step and self.trace_writer:
                self.trace_writer.update_step_status(
                    step.id,
                    "failed",
                    error_code="RERANK_ERROR",
                    error_message=str(e),
                )
            raise
