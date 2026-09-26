""" client_address

The address a request came from, as far as the deployment can vouch for it.

The socket peer is the client unless it is one of the configured trusted
proxies. Behind them, ``X-Forwarded-For`` is read from the right: every hop a
trusted proxy appended is skipped, and the first address that is not a trusted
proxy is the client. Anything to its left was written by the client itself and
is not believed, so a caller cannot pick the address an allowlist sees.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Sequence
from functools import lru_cache

from starlette.requests import HTTPConnection

_Network = ipaddress.IPv4Network | ipaddress.IPv6Network
_Address = ipaddress.IPv4Address | ipaddress.IPv6Address


@lru_cache(maxsize=32)
def _networks(entries: tuple[str, ...]) -> tuple[_Network, ...]:
    return tuple(ipaddress.ip_network(entry, strict=False) for entry in entries)


def _parse(value: str) -> _Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def _trusted(address: _Address, networks: Iterable[_Network]) -> bool:
    return any(address in network for network in networks)


def client_address(connection: HTTPConnection, trusted_proxies: Sequence[str]) -> str | None:
    """The client's address, or None when it cannot be established."""

    peer = connection.client.host if connection.client else None
    networks = _networks(tuple(trusted_proxies))
    peer_address = _parse(peer) if peer else None
    if peer_address is None or not networks or not _trusted(peer_address, networks):
        return peer
    hops = [
        hop.strip()
        for header in connection.headers.getlist("x-forwarded-for")
        for hop in header.split(",")
        if hop.strip()
    ]
    for hop in reversed(hops):
        address = _parse(hop)
        if address is None:
            # A hop no proxy of ours would write: the chain cannot be vouched
            # for past this point.
            return None
        if not _trusted(address, networks):
            return str(address)
    # Every hop is a trusted proxy: the request started inside the perimeter.
    return str(_parse(hops[0])) if hops else peer


def address_allowed(address: str | None, allowlist: Sequence[str]) -> bool:
    """Whether ``address`` falls inside one of the ``allowlist`` ranges."""

    parsed = _parse(address) if address else None
    if parsed is None:
        return False
    try:
        networks = _networks(tuple(allowlist))
    except ValueError:
        # Entries are validated when a key is saved; one that is not a range
        # anyway admits nobody rather than failing open.
        return False
    return _trusted(parsed, networks)
