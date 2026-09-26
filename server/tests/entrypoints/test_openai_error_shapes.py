"""Errors keep the SOIT envelope on /api and take the OpenAI shape on /v1."""

from __future__ import annotations

import pytest

from app.api.v1.billing.dependencies import get_credit_service
from app.kernel.commons.errors import RateLimitExceededError
from app.main import app
from app.middleware.openai_errors import openai_error_body, openai_error_type


class _Throttled:
    async def get_balance(self):
        raise RateLimitExceededError(
            "Rate limit exceeded: 10 requests per 60 seconds",
            {"limit": 10, "window_seconds": 60, "retry_after": 42},
        )


@pytest.mark.asyncio
async def test_a_rate_limit_answers_429_with_retry_after(async_client) -> None:
    app.dependency_overrides[get_credit_service] = lambda: _Throttled()
    try:
        response = await async_client.get("/api/v1/billing/credits/balance")
    finally:
        app.dependency_overrides.pop(get_credit_service, None)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "42"
    body = response.json()
    assert body["success"] is False
    assert body["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_an_unknown_v1_route_answers_in_the_openai_shape(async_client) -> None:
    response = await async_client.get("/v1/definitely-not-a-route")

    assert response.status_code == 404
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["type"] == "invalid_request_error"
    assert body["error"]["code"] == "not_found"
    assert "message" in body["error"] and "param" in body["error"]


@pytest.mark.asyncio
async def test_the_api_surface_keeps_the_soit_envelope(async_client) -> None:
    response = await async_client.get("/api/v1/definitely-not-a-route")

    assert response.status_code == 404
    assert response.json()["success"] is False


def test_openai_error_types_follow_the_status() -> None:
    assert openai_error_type(401) == "authentication_error"
    assert openai_error_type(402) == "insufficient_quota"
    assert openai_error_type(403) == "permission_error"
    assert openai_error_type(429) == "rate_limit_error"
    assert openai_error_type(503) == "api_error"
    body = openai_error_body(
        400,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": [{"field": "body.messages", "message": "Field required"}]},
    )
    assert body["error"]["param"] == "messages"
    assert body["error"]["code"] == "validation_error"
