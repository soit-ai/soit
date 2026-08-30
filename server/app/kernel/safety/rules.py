"""rules

A built-in content safety provider that needs no external service.

What it is: deterministic pattern matching for the things that are unambiguous
in text -- credentials, and the identifiers that are personal data in every
jurisdiction. It runs in-process, adds no network call, and its findings go
into run evidence like any other governed decision.

What it is not: a classifier. It cannot judge whether a sentence is abusive,
whether a request is a jailbreak, or whether a document is confidential. A
deployment that needs those plugs in a service through the same port, and this
provider steps aside.

Because a pattern can be wrong, the defaults are asymmetric:

- Credentials are redacted. A string shaped exactly like a private key or an
  API token has no business in a prompt or a tool argument, and redacting a
  false positive costs a value nobody wanted sent anyway.
- Personal data is recorded, not altered. Emails and phone numbers are the
  ordinary content of real work -- a support agent reading a customer's email
  address is the job. Silently rewriting them would corrupt the work while
  looking like nothing happened, so the finding is reported and the deployment
  decides whether to escalate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.kernel.ports.safety.interface import (
    ContentSafetyPort,
    SafetyDecision,
    SafetyDirection,
    SafetyFinding,
    SafetyVerdict,
)

PROVIDER = "builtin.rules"


class SafetyAction(str, Enum):
    """What a deployment wants done when a class of pattern matches."""

    OBSERVE = "observe"
    """Record the finding and pass the content through unchanged."""

    REDACT = "redact"
    """Replace each match, and pass the rest through."""

    BLOCK = "block"
    """Refuse the content."""


@dataclass(frozen=True)
class _Rule:
    category: str
    severity: str
    pattern: re.Pattern[str]
    validate: Any = None
    """Optional callable on the match text; a False return drops the match."""


def _luhn(digits: str) -> bool:
    """Return True when a digit string satisfies the Luhn checksum.

    Card-shaped numbers are common in ordinary text -- order ids, ticket
    numbers -- and the checksum is what separates a card from a coincidence.
    """
    body = [int(char) for char in digits if char.isdigit()]
    if len(body) < 13:
        return False
    total = 0
    for index, digit in enumerate(reversed(body)):
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


_CN_ID_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_CN_ID_CHECKS = "10X98765432"


def _cn_national_id(value: str) -> bool:
    """Return True when an 18-character mainland China ID checksum holds."""
    if len(value) != 18:
        return False
    body, check = value[:17], value[17].upper()
    if not body.isdigit():
        return False
    total = sum(int(char) * weight for char, weight in zip(body, _CN_ID_WEIGHTS, strict=True))
    return _CN_ID_CHECKS[total % 11] == check


RULES: tuple[_Rule, ...] = (
    # --- credentials -----------------------------------------------------
    _Rule(
        "secret.private_key",
        "high",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    ),
    _Rule("secret.aws_access_key_id", "high", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    _Rule("secret.github_token", "high", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    _Rule("secret.slack_token", "high", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    _Rule("secret.google_api_key", "high", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    _Rule("secret.openai_api_key", "high", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    _Rule(
        "secret.jwt",
        "high",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    ),
    _Rule(
        "secret.bearer_token",
        "high",
        # The header form only: a bare word after "bearer" in prose is not a
        # credential, and matching it would redact sentences.
        re.compile(r"(?i)\bauthorization\s*:\s*bearer\s+[A-Za-z0-9._\-]{20,}"),
    ),
    # --- personal data ---------------------------------------------------
    _Rule(
        "pii.email",
        "medium",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    ),
    _Rule(
        "pii.credit_card",
        "high",
        re.compile(r"\b(?:\d[ \-]?){12,18}\d\b"),
        _luhn,
    ),
    _Rule(
        "pii.national_id.cn",
        "high",
        re.compile(r"\b\d{17}[\dXx]\b"),
        _cn_national_id,
    ),
    _Rule("pii.ssn.us", "high", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    _Rule(
        "pii.phone",
        "medium",
        # International form, and mainland China mobiles, which do not carry a
        # country prefix in most real text.
        re.compile(r"(?:\+\d{1,3}[ \-]?\d{6,14}\b)|(?:\b1[3-9]\d{9}\b)"),
    ),
)


def scan_text(text: str) -> list[tuple[_Rule, str]]:
    """Return every rule match in the text, with the matched substring."""
    matches: list[tuple[_Rule, str]] = []
    for rule in RULES:
        for found in rule.pattern.finditer(text):
            value = found.group(0)
            if rule.validate is not None and not rule.validate(value):
                continue
            matches.append((rule, value))
    return matches


def _redact(text: str, matches: list[tuple[_Rule, str]]) -> str:
    """Replace each matched value with a marker naming what it was.

    Longest first, so a value contained inside another is not left behind as a
    fragment of an already-replaced string.
    """
    redacted = text
    for rule, value in sorted(matches, key=lambda item: len(item[1]), reverse=True):
        redacted = redacted.replace(value, f"[redacted:{rule.category}]")
    return redacted


_ORDER = {SafetyAction.OBSERVE: 0, SafetyAction.REDACT: 1, SafetyAction.BLOCK: 2}


class RuleContentSafetyPort(ContentSafetyPort):
    """Match credentials and personal identifiers without leaving the process."""

    def __init__(
        self,
        *,
        secret_action: SafetyAction = SafetyAction.REDACT,
        pii_action: SafetyAction = SafetyAction.OBSERVE,
    ) -> None:
        self.secret_action = secret_action
        self.pii_action = pii_action

    def _action_for(self, category: str) -> SafetyAction:
        return self.secret_action if category.startswith("secret.") else self.pii_action

    async def inspect(
        self,
        text: str,
        *,
        direction: SafetyDirection,
        **kwargs: Any,
    ) -> SafetyVerdict:
        """Inspect one piece of content and return the verdict to apply."""
        if not text:
            return SafetyVerdict(decision=SafetyDecision.ALLOW, provider=PROVIDER)

        matches = scan_text(text)
        if not matches:
            return SafetyVerdict(decision=SafetyDecision.ALLOW, provider=PROVIDER)

        findings: list[SafetyFinding] = []
        seen: set[str] = set()
        decision_action = SafetyAction.OBSERVE
        redactable: list[tuple[_Rule, str]] = []
        for rule, value in matches:
            action = self._action_for(rule.category)
            if _ORDER[action] > _ORDER[decision_action]:
                decision_action = action
            if action is SafetyAction.REDACT:
                redactable.append((rule, value))
            if rule.category in seen:
                continue
            seen.add(rule.category)
            findings.append(
                SafetyFinding(
                    category=rule.category,
                    severity=rule.severity,
                    # Counts, never the matched text: recording it here would
                    # recreate the exposure the check exists to stop.
                    detail=f"{sum(1 for item in matches if item[0].category == rule.category)} match(es)",
                )
            )

        if decision_action is SafetyAction.BLOCK:
            return SafetyVerdict(
                decision=SafetyDecision.BLOCK,
                findings=findings,
                provider=PROVIDER,
                metadata={"direction": direction.value},
            )
        if decision_action is SafetyAction.REDACT:
            return SafetyVerdict(
                decision=SafetyDecision.REDACT,
                findings=findings,
                redacted_text=_redact(text, redactable),
                provider=PROVIDER,
                metadata={"direction": direction.value},
            )
        return SafetyVerdict(
            decision=SafetyDecision.ALLOW,
            findings=findings,
            provider=PROVIDER,
            metadata={"direction": direction.value},
        )
