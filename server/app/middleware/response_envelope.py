"""response_envelope

Standard API response envelope middleware.
"""

from __future__ import annotations

import json
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.api.v1.schemas.response import success_envelope, is_enveloped
from app.kernel.observability.context import get_log_context


class ResponseEnvelopeMiddleware(BaseHTTPMiddleware):
    """Wrap JSON responses in the standard API envelope."""

    def _resolve_trace_ids(self, request: Request) -> tuple[Optional[str], Optional[str]]:
        log_ctx = get_log_context()
        request_id = getattr(request.state, "request_id", None) or log_ctx.get("request_id")
        run_id = getattr(request.state, "run_id", None) or log_ctx.get("run_id")
        return request_id, run_id

    def _should_wrap(self, response: Response) -> bool:
        if response.status_code < 200 or response.status_code >= 400:
            return False
        if response.status_code in {204, 205, 304}:
            return False
        media_type = response.media_type or response.headers.get("content-type", "")
        if media_type and "application/json" not in media_type:
            return False
        return True

    async def _read_body(self, response: Response) -> bytes:
        if hasattr(response, "body"):
            body = getattr(response, "body", None)
            if body not in (None, b""):
                return body
        if hasattr(response, "body_iterator"):
            chunks = []
            async for chunk in response.body_iterator:
                if isinstance(chunk, memoryview):
                    chunk = bytes(chunk)
                elif isinstance(chunk, str):
                    chunk = chunk.encode("utf-8")
                chunks.append(chunk)
            return b"".join(chunks)
        return b""

    def _copy_headers(self, response: Response, target: Response) -> None:
        for key, value in response.headers.items():
            lower_key = key.lower()
            if lower_key in {"content-length"}:
                continue
            if lower_key == "content-type":
                continue
            target.headers[key] = value

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        if request.app.openapi_url and request.url.path == request.app.openapi_url:
            return response
        if not self._should_wrap(response):
            return response
        raw_body = await self._read_body(response)
        if raw_body in (None, b""):
            payload = None
        else:
            try:
                payload = json.loads(raw_body)
            except Exception:
                passthrough = Response(
                    content=raw_body,
                    status_code=response.status_code,
                    media_type=response.media_type,
                )
                self._copy_headers(response, passthrough)
                return passthrough

        if is_enveloped(payload):
            passthrough = JSONResponse(
                content=payload,
                status_code=response.status_code,
                media_type=response.media_type,
            )
            self._copy_headers(response, passthrough)
            return passthrough

        request_id, run_id = self._resolve_trace_ids(request)
        envelope = success_envelope(
            data=payload,
            request_id=request_id,
            run_id=run_id,
        )
        wrapped = JSONResponse(
            content=envelope,
            status_code=response.status_code,
            media_type=response.media_type,
        )
        self._copy_headers(response, wrapped)
        return wrapped
