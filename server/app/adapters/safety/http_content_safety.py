"""Content safety adapter backed by an external HTTP service.

SOIT does not classify content itself. This adapter forwards text to a service
the deployment operates and maps its answer onto the kernel verdict. The call
goes through the governed egress client like every other outbound path, so the
safety service cannot become a hole in the egress policy.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.http.governed_client import governed_httpx_client
from app.kernel.contracts.context import RequestContext
from app.kernel.ports.safety.interface import (
    ContentSafetyPort,
    SafetyDecision,
    SafetyDirection,
    SafetyFinding,
    SafetyVerdict,
)

RESOURCE_REF = "safety:content"


class HttpContentSafetyPort(ContentSafetyPort):
    """Delegate inspection to a configured HTTP endpoint."""

    def __init__(
        self,
        *,
        ctx: RequestContext,
        endpoint: str,
        provider: str = "http",
        timeout_seconds: float = 10.0,
        fail_closed: bool = True,
        api_key: str | None = None,
    ) -> None:
        self.ctx = ctx
        self.endpoint = endpoint
        self.provider = provider
        self.timeout_seconds = timeout_seconds
        self.fail_closed = fail_closed
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}

    async def inspect(
        self,
        text: str,
        *,
        direction: SafetyDirection,
        **kwargs: Any,
    ) -> SafetyVerdict:
        payload = {
            "text": text,
            "direction": direction.value,
            "tenant_id": self.ctx.tenant_id,
            "workspace_id": self.ctx.workspace_id,
        }
        run_id = kwargs.get("run_id")
        if run_id:
            payload["run_id"] = str(run_id)

        try:
            async with governed_httpx_client(
                ctx=self.ctx,
                resource_ref=RESOURCE_REF,
                timeout=httpx.Timeout(self.timeout_seconds),
            ) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()
        except Exception as exc:
            # An unreachable classifier must not silently disable the check.
            # Deployments that prefer availability over enforcement can opt out
            # explicitly, but the default is to refuse the content.
            if self.fail_closed:
                return SafetyVerdict(
                    decision=SafetyDecision.BLOCK,
                    findings=[
                        SafetyFinding(
                            category="safety.provider_unavailable",
                            severity="error",
                            detail=type(exc).__name__,
                        )
                    ],
                    provider=self.provider,
                )
            return SafetyVerdict(
                decision=SafetyDecision.ALLOW,
                findings=[
                    SafetyFinding(
                        category="safety.provider_unavailable",
                        severity="warning",
                        detail=type(exc).__name__,
                    )
                ],
                provider=self.provider,
            )

        return self._to_verdict(data)

    def _to_verdict(self, data: Any) -> SafetyVerdict:
        if not isinstance(data, dict):
            return SafetyVerdict(decision=SafetyDecision.ALLOW, provider=self.provider)

        raw_decision = str(data.get("decision") or "allow").strip().lower()
        try:
            decision = SafetyDecision(raw_decision)
        except ValueError:
            # An unrecognised decision is not treated as permission.
            decision = (
                SafetyDecision.BLOCK if self.fail_closed else SafetyDecision.ALLOW
            )

        findings: list[SafetyFinding] = []
        for entry in data.get("findings") or []:
            if not isinstance(entry, dict):
                continue
            category = str(entry.get("category") or "").strip()
            if not category:
                continue
            findings.append(
                SafetyFinding(
                    category=category,
                    severity=str(entry.get("severity") or "unknown"),
                    detail=(
                        str(entry["detail"]) if entry.get("detail") is not None else None
                    ),
                )
            )

        redacted = data.get("redacted_text")
        return SafetyVerdict(
            decision=decision,
            findings=findings,
            redacted_text=str(redacted) if isinstance(redacted, str) else None,
            provider=self.provider,
        )
