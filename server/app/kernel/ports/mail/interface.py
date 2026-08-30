"""Port for the instance's own outbound mail.

Distinct from notification endpoints, which belong to a workspace and are
configured by its members. Password resets and invitations cannot borrow one:
the recipient may not be a member yet, and a workspace must not be able to
intercept an identity mail by pointing its endpoint somewhere.

There is no fallback. When no mail outlet is configured the features that need
one report that they are unavailable, rather than accepting a request and
silently dropping it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MailMessage:
    """One message the instance sends on its own behalf."""

    to: str
    subject: str
    body: str
    kind: str
    """What this mail is for: password_reset, invitation, email_verification."""


class MailPort(Protocol):
    """Send mail as the instance."""

    async def send(self, message: MailMessage) -> None:
        """Deliver the message.

        Raises:
            Exception: When delivery fails. Callers decide whether that should
                fail the request or only be recorded; a password reset must not
                reveal whether the address exists, so it records and returns.
        """
