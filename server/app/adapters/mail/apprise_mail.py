"""Send the instance's own mail through Apprise.

Apprise is already a dependency for notification delivery, and its `mailto://`
URLs cover SMTP, so this adds no new supply chain for a feature that mostly has
to work in whatever a self-hosted operator already runs.

The configured URL carries credentials, so it is never logged or returned. What
is recorded is that a message was sent, to whom, and whether it worked.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from apprise import Apprise

from app.kernel.ports.mail.interface import MailMessage

logger = logging.getLogger(__name__)

Sender = Callable[..., bool]


def _send(url: str, *, title: str, body: str) -> bool:
    notifier = Apprise()
    if not notifier.add(url):
        raise RuntimeError("The configured mail URL was not accepted")
    return bool(notifier.notify(title=title, body=body))


def _with_recipient(url: str, recipient: str) -> str:
    """Point a mailto:// URL at one address.

    The configured URL supplies the server and the sender; the recipient is
    per message. A `to` already in the URL is replaced rather than added to, so
    an operator's default cannot silently copy every reset mail somewhere else.
    """
    parsed = urlparse(url)
    query = [(key, value) for key, value in parse_qsl(parsed.query) if key.lower() != "to"]
    query.append(("to", recipient))
    return urlunparse(parsed._replace(query=urlencode(query)))


class AppriseMailPort:
    """Instance mail over an Apprise URL."""

    def __init__(self, url: str, *, sender: Sender | None = None) -> None:
        self._url = url
        self._sender = sender or _send

    async def send(self, message: MailMessage) -> None:
        """Deliver one message, or raise.

        Raising rather than returning a flag: a caller that must not reveal
        whether an address exists catches it, and one that should fail loudly
        lets it through.
        """
        url = _with_recipient(self._url, message.to)
        delivered = await asyncio.to_thread(
            self._sender,
            url,
            title=message.subject,
            body=message.body,
        )
        if not delivered:
            raise RuntimeError("The mail provider rejected the message")
