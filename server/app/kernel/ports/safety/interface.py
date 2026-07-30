""" interface

Content safety port interface.

SOIT does not detect unsafe content or PII itself. This port lets a deployment
plug in a service that does, and makes the outcome part of the run's evidence
rather than an invisible side effect. Without a configured adapter the platform
states plainly that it provides no such capability.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SafetyDirection(str, Enum):
    """Which side of a model or tool boundary the text crossed."""

    INBOUND = "inbound"
    """Content entering the runtime (user input, retrieved documents)."""

    OUTBOUND = "outbound"
    """Content leaving the runtime (model output, tool arguments)."""


class SafetyDecision(str, Enum):
    """What the deployment's policy says should happen."""

    ALLOW = "allow"
    REDACT = "redact"
    BLOCK = "block"


@dataclass(frozen=True)
class SafetyFinding:
    """One category the provider matched."""

    category: str
    """Provider category, e.g. "pii.email" or "violence"."""

    severity: str = "unknown"
    """Provider severity label; not normalised across providers."""

    detail: str | None = None
    """Short human-readable note. Must not repeat the matched text."""


@dataclass(frozen=True)
class SafetyVerdict:
    """Outcome of one content check."""

    decision: SafetyDecision
    findings: list[SafetyFinding] = field(default_factory=list)
    redacted_text: str | None = None
    """Replacement text when the decision is REDACT."""

    provider: str | None = None
    """Adapter identity, recorded so evidence says who decided."""

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return self.decision is SafetyDecision.BLOCK

    def evidence(self) -> dict[str, Any]:
        """Render the verdict for run evidence.

        The matched text is deliberately excluded: recording detected PII into
        the audit trail would recreate the exposure the check exists to stop.
        """
        return {
            "decision": self.decision.value,
            "provider": self.provider,
            "findings": [
                {
                    "category": finding.category,
                    "severity": finding.severity,
                    "detail": finding.detail,
                }
                for finding in self.findings
            ],
        }


class ContentSafetyPort(ABC):
    """Port for an external content safety and PII service."""

    @abstractmethod
    async def inspect(
        self,
        text: str,
        *,
        direction: SafetyDirection,
        **kwargs: Any,
    ) -> SafetyVerdict:
        """Inspect one piece of content and return the policy verdict.

        Args:
            text: Content to inspect.
            direction: Whether the content is entering or leaving the runtime.
            **kwargs: Adapter-specific context (run_id, tenant_id, ...).

        Returns:
            The verdict to apply.
        """
        raise NotImplementedError
