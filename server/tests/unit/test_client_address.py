"""The client address comes from the socket unless a trusted proxy vouches for another."""

from __future__ import annotations

from starlette.requests import Request

from app.auth.client_address import address_allowed, client_address

PROXIES = ["10.0.0.0/8"]


def _request(peer: str, *forwarded: str) -> Request:
    headers = [(b"x-forwarded-for", value.encode()) for value in forwarded]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/models",
            "headers": headers,
            "query_string": b"",
            "client": (peer, 50000),
        }
    )


def test_without_trusted_proxies_the_socket_peer_is_the_client() -> None:
    assert client_address(_request("198.51.100.7", "203.0.113.1"), []) == "198.51.100.7"


def test_a_header_from_an_untrusted_peer_is_ignored() -> None:
    assert client_address(_request("198.51.100.7", "203.0.113.1"), PROXIES) == "198.51.100.7"


def test_behind_a_trusted_proxy_the_nearest_untrusted_hop_is_the_client() -> None:
    request = _request("10.0.0.2", "203.0.113.1, 198.51.100.7, 10.0.0.9")

    assert client_address(request, PROXIES) == "198.51.100.7"


def test_hops_split_across_headers_are_read_as_one_chain() -> None:
    request = _request("10.0.0.2", "192.0.2.4", "198.51.100.7")

    assert client_address(request, PROXIES) == "198.51.100.7"


def test_a_malformed_hop_leaves_the_address_unknown() -> None:
    assert client_address(_request("10.0.0.2", "not-an-address"), PROXIES) is None


def test_a_request_from_inside_the_perimeter_keeps_the_first_hop() -> None:
    assert client_address(_request("10.0.0.2", "10.1.1.1, 10.0.0.9"), PROXIES) == "10.1.1.1"


def test_allowlists_match_addresses_and_ranges() -> None:
    allowlist = ["203.0.113.0/24", "2001:db8::/32", "192.0.2.10"]

    assert address_allowed("203.0.113.44", allowlist)
    assert address_allowed("2001:db8::1", allowlist)
    assert address_allowed("192.0.2.10", allowlist)
    assert not address_allowed("192.0.2.11", allowlist)
    assert not address_allowed(None, allowlist)
    assert not address_allowed("203.0.113.44", ["not-a-range"])
